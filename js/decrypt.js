/**
 * This is wrapper for decrypting encoded notes, made from scripts of the Evernote Web Client
 *
 * Usage:
 * decrypt(cipher, length, password, base64_data);
 * Throws exception for bad password.
 *
 * Sources taken from these files:
 * https://www.evernote.com/redesign/global/js/aes-crypto.js
 * https://www.evernote.com/redesign/global/js/decrypt.js
 *
 * Good articles:
 * https://evernote.com/contact/support/kb/#/article/23480996
 * http://soundly.me/decoding-the-Evernote-en-crypt-field-payload/
 */


var decrypt = (function() {

    var evernoteAesCrypto = (function() {
        /**
         * Taken from vendor/sjcl/core.js of common-editor (branch: develop) as of commit
         * 69296310. This is a custom SJCL build that includes CBC mode. Changes:
         *   - Wrap in define block. Return sjcl object.
         *   - Add sjcl.misc.pbkdf2_async for an IE7/8 fix (WEB-21996).
         */
        var sjcl = (function($) {
          /** @fileOverview Javascript cryptography implementation.
           *
           * Crush to remove comments, shorten variable names and
           * generally reduce transmission size.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */


          /*jslint indent: 2, bitwise: false, nomen: false, plusplus: false, white: false, regexp: false */
          /*global document, window, escape, unescape */

          /** @namespace The Stanford Javascript Crypto Library, top-level namespace. */
          var sjcl = {
            /** @namespace Symmetric ciphers. */
            cipher: {},

            /** @namespace Hash functions.  Right now only SHA256 is implemented. */
            hash: {},

            /** @namespace Key exchange functions.  Right now only SRP is implemented. */
            keyexchange: {},

            /** @namespace Block cipher modes of operation. */
            mode: {},

            /** @namespace Miscellaneous.  HMAC and PBKDF2. */
            misc: {},

            /**
             * @namespace Bit array encoders and decoders.
             *
             * @description
             * The members of this namespace are functions which translate between
             * SJCL's bitArrays and other objects (usually strings).  Because it
             * isn't always clear which direction is encoding and which is decoding,
             * the method names are "fromBits" and "toBits".
             */
            codec: {},

            /** @namespace Exceptions. */
            exception: {
              /** @constructor Ciphertext is corrupt. */
              corrupt: function(message) {
                this.toString = function() { return "CORRUPT: "+this.message; };
                this.message = message;
              },

              /** @constructor Invalid parameter. */
              invalid: function(message) {
                this.toString = function() { return "INVALID: "+this.message; };
                this.message = message;
              },

              /** @constructor Bug or missing feature in SJCL. @constructor */
              bug: function(message) {
                this.toString = function() { return "BUG: "+this.message; };
                this.message = message;
              },

              /** @constructor Something isn't ready. */
              notReady: function(message) {
                this.toString = function() { return "NOT READY: "+this.message; };
                this.message = message;
              }
            }
          };

          if(typeof module != 'undefined' && module.exports){
            module.exports = sjcl;
          }
          /** @fileOverview Low-level AES implementation.
           *
           * This file contains a low-level implementation of AES, optimized for
           * size and for efficiency on several browsers.  It is based on
           * OpenSSL's aes_core.c, a public-domain implementation by Vincent
           * Rijmen, Antoon Bosselaers and Paulo Barreto.
           *
           * An older version of this implementation is available in the public
           * domain, but this one is (c) Emily Stark, Mike Hamburg, Dan Boneh,
           * Stanford University 2008-2010 and BSD-licensed for liability
           * reasons.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /**
           * Schedule out an AES key for both encryption and decryption.  This
           * is a low-level class.  Use a cipher mode to do bulk encryption.
           *
           * @constructor
           * @param {Array} key The key as an array of 4, 6 or 8 words.
           *
           * @class Advanced Encryption Standard (low-level interface)
           */
          sjcl.cipher.aes = function (key) {
            if (!this._tables[0][0][0]) {
              this._precompute();
            }

            var i, j, tmp,
              encKey, decKey,
              sbox = this._tables[0][4], decTable = this._tables[1],
              keyLen = key.length, rcon = 1;

            if (keyLen !== 4 && keyLen !== 6 && keyLen !== 8) {
              throw new sjcl.exception.invalid("invalid aes key size");
            }

            this._key = [encKey = key.slice(0), decKey = []];

            // schedule encryption keys
            for (i = keyLen; i < 4 * keyLen + 28; i++) {
              tmp = encKey[i-1];

              // apply sbox
              if (i%keyLen === 0 || (keyLen === 8 && i%keyLen === 4)) {
                tmp = sbox[tmp>>>24]<<24 ^ sbox[tmp>>16&255]<<16 ^ sbox[tmp>>8&255]<<8 ^ sbox[tmp&255];

                // shift rows and add rcon
                if (i%keyLen === 0) {
                  tmp = tmp<<8 ^ tmp>>>24 ^ rcon<<24;
                  rcon = rcon<<1 ^ (rcon>>7)*283;
                }
              }

              encKey[i] = encKey[i-keyLen] ^ tmp;
            }

            // schedule decryption keys
            for (j = 0; i; j++, i--) {
              tmp = encKey[j&3 ? i : i - 4];
              if (i<=4 || j<4) {
                decKey[j] = tmp;
              } else {
                decKey[j] = decTable[0][sbox[tmp>>>24      ]] ^
                            decTable[1][sbox[tmp>>16  & 255]] ^
                            decTable[2][sbox[tmp>>8   & 255]] ^
                            decTable[3][sbox[tmp      & 255]];
              }
            }
          };

          sjcl.cipher.aes.prototype = {
            // public
            /* Something like this might appear here eventually
            name: "AES",
            blockSize: 4,
            keySizes: [4,6,8],
            */

            /**
             * Encrypt an array of 4 big-endian words.
             * @param {Array} data The plaintext.
             * @return {Array} The ciphertext.
             */
            encrypt:function (data) { return this._crypt(data,0); },

            /**
             * Decrypt an array of 4 big-endian words.
             * @param {Array} data The ciphertext.
             * @return {Array} The plaintext.
             */
            decrypt:function (data) { return this._crypt(data,1); },

            /**
             * The expanded S-box and inverse S-box tables.  These will be computed
             * on the client so that we don't have to send them down the wire.
             *
             * There are two tables, _tables[0] is for encryption and
             * _tables[1] is for decryption.
             *
             * The first 4 sub-tables are the expanded S-box with MixColumns.  The
             * last (_tables[01][4]) is the S-box itself.
             *
             * @private
             */
            _tables: [[[],[],[],[],[]],[[],[],[],[],[]]],

            /**
             * Expand the S-box tables.
             *
             * @private
             */
            _precompute: function () {
             var encTable = this._tables[0], decTable = this._tables[1],
                 sbox = encTable[4], sboxInv = decTable[4],
                 i, x, xInv, d=[], th=[], x2, x4, x8, s, tEnc, tDec;

              // Compute double and third tables
             for (i = 0; i < 256; i++) {
               th[( d[i] = i<<1 ^ (i>>7)*283 )^i]=i;
             }

             for (x = xInv = 0; !sbox[x]; x ^= x2 || 1, xInv = th[xInv] || 1) {
               // Compute sbox
               s = xInv ^ xInv<<1 ^ xInv<<2 ^ xInv<<3 ^ xInv<<4;
               s = s>>8 ^ s&255 ^ 99;
               sbox[x] = s;
               sboxInv[s] = x;

               // Compute MixColumns
               x8 = d[x4 = d[x2 = d[x]]];
               tDec = x8*0x1010101 ^ x4*0x10001 ^ x2*0x101 ^ x*0x1010100;
               tEnc = d[s]*0x101 ^ s*0x1010100;

               for (i = 0; i < 4; i++) {
                 encTable[i][x] = tEnc = tEnc<<24 ^ tEnc>>>8;
                 decTable[i][s] = tDec = tDec<<24 ^ tDec>>>8;
               }
             }

             // Compactify.  Considerable speedup on Firefox.
             for (i = 0; i < 5; i++) {
               encTable[i] = encTable[i].slice(0);
               decTable[i] = decTable[i].slice(0);
             }
            },

            /**
             * Encryption and decryption core.
             * @param {Array} input Four words to be encrypted or decrypted.
             * @param dir The direction, 0 for encrypt and 1 for decrypt.
             * @return {Array} The four encrypted or decrypted words.
             * @private
             */
            _crypt:function (input, dir) {
              if (input.length !== 4) {
                throw new sjcl.exception.invalid("invalid aes block size");
              }

              var key = this._key[dir],
                  // state variables a,b,c,d are loaded with pre-whitened data
                  a = input[0]           ^ key[0],
                  b = input[dir ? 3 : 1] ^ key[1],
                  c = input[2]           ^ key[2],
                  d = input[dir ? 1 : 3] ^ key[3],
                  a2, b2, c2,

                  nInnerRounds = key.length/4 - 2,
                  i,
                  kIndex = 4,
                  out = [0,0,0,0],
                  table = this._tables[dir],

                  // load up the tables
                  t0    = table[0],
                  t1    = table[1],
                  t2    = table[2],
                  t3    = table[3],
                  sbox  = table[4];

              // Inner rounds.  Cribbed from OpenSSL.
              for (i = 0; i < nInnerRounds; i++) {
                a2 = t0[a>>>24] ^ t1[b>>16 & 255] ^ t2[c>>8 & 255] ^ t3[d & 255] ^ key[kIndex];
                b2 = t0[b>>>24] ^ t1[c>>16 & 255] ^ t2[d>>8 & 255] ^ t3[a & 255] ^ key[kIndex + 1];
                c2 = t0[c>>>24] ^ t1[d>>16 & 255] ^ t2[a>>8 & 255] ^ t3[b & 255] ^ key[kIndex + 2];
                d  = t0[d>>>24] ^ t1[a>>16 & 255] ^ t2[b>>8 & 255] ^ t3[c & 255] ^ key[kIndex + 3];
                kIndex += 4;
                a=a2; b=b2; c=c2;
              }

              // Last round.
              for (i = 0; i < 4; i++) {
                out[dir ? 3&-i : i] =
                  sbox[a>>>24      ]<<24 ^
                  sbox[b>>16  & 255]<<16 ^
                  sbox[c>>8   & 255]<<8  ^
                  sbox[d      & 255]     ^
                  key[kIndex++];
                a2=a; a=b; b=c; c=d; d=a2;
              }

              return out;
            }
          };

          /** @fileOverview Arrays of bits, encoded as arrays of Numbers.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /** @namespace Arrays of bits, encoded as arrays of Numbers.
           *
           * @description
           * <p>
           * These objects are the currency accepted by SJCL's crypto functions.
           * </p>
           *
           * <p>
           * Most of our crypto primitives operate on arrays of 4-byte words internally,
           * but many of them can take arguments that are not a multiple of 4 bytes.
           * This library encodes arrays of bits (whose size need not be a multiple of 8
           * bits) as arrays of 32-bit words.  The bits are packed, big-endian, into an
           * array of words, 32 bits at a time.  Since the words are double-precision
           * floating point numbers, they fit some extra data.  We use this (in a private,
           * possibly-changing manner) to encode the number of bits actually  present
           * in the last word of the array.
           * </p>
           *
           * <p>
           * Because bitwise ops clear this out-of-band data, these arrays can be passed
           * to ciphers like AES which want arrays of words.
           * </p>
           */
          sjcl.bitArray = {
            /**
             * Array slices in units of bits.
             * @param {bitArray} a The array to slice.
             * @param {Number} bstart The offset to the start of the slice, in bits.
             * @param {Number} bend The offset to the end of the slice, in bits.  If this is undefined,
             * slice until the end of the array.
             * @return {bitArray} The requested slice.
             */
            bitSlice: function (a, bstart, bend) {
              a = sjcl.bitArray._shiftRight(a.slice(bstart/32), 32 - (bstart & 31)).slice(1);
              return (bend === undefined) ? a : sjcl.bitArray.clamp(a, bend-bstart);
            },

            /**
             * Extract a number packed into a bit array.
             * @param {bitArray} a The array to slice.
             * @param {Number} bstart The offset to the start of the slice, in bits.
             * @param {Number} length The length of the number to extract.
             * @return {Number} The requested slice.
             */
            extract: function(a, bstart, blength) {
              // FIXME: this Math.floor is not necessary at all, but for some reason
              // seems to suppress a bug in the Chromium JIT.
              var x, sh = Math.floor((-bstart-blength) & 31);
              if ((bstart + blength - 1 ^ bstart) & -32) {
                // it crosses a boundary
                x = (a[bstart/32|0] << (32 - sh)) ^ (a[bstart/32+1|0] >>> sh);
              } else {
                // within a single word
                x = a[bstart/32|0] >>> sh;
              }
              return x & ((1<<blength) - 1);
            },

            /**
             * Concatenate two bit arrays.
             * @param {bitArray} a1 The first array.
             * @param {bitArray} a2 The second array.
             * @return {bitArray} The concatenation of a1 and a2.
             */
            concat: function (a1, a2) {
              if (a1.length === 0 || a2.length === 0) {
                return a1.concat(a2);
              }

              var out, i, last = a1[a1.length-1], shift = sjcl.bitArray.getPartial(last);
              if (shift === 32) {
                return a1.concat(a2);
              } else {
                return sjcl.bitArray._shiftRight(a2, shift, last|0, a1.slice(0,a1.length-1));
              }
            },

            /**
             * Find the length of an array of bits.
             * @param {bitArray} a The array.
             * @return {Number} The length of a, in bits.
             */
            bitLength: function (a) {
              var l = a.length, x;
              if (l === 0) { return 0; }
              x = a[l - 1];
              return (l-1) * 32 + sjcl.bitArray.getPartial(x);
            },

            /**
             * Truncate an array.
             * @param {bitArray} a The array.
             * @param {Number} len The length to truncate to, in bits.
             * @return {bitArray} A new array, truncated to len bits.
             */
            clamp: function (a, len) {
              if (a.length * 32 < len) { return a; }
              a = a.slice(0, Math.ceil(len / 32));
              var l = a.length;
              len = len & 31;
              if (l > 0 && len) {
                a[l-1] = sjcl.bitArray.partial(len, a[l-1] & 0x80000000 >> (len-1), 1);
              }
              return a;
            },

            /**
             * Make a partial word for a bit array.
             * @param {Number} len The number of bits in the word.
             * @param {Number} x The bits.
             * @param {Number} [0] _end Pass 1 if x has already been shifted to the high side.
             * @return {Number} The partial word.
             */
            partial: function (len, x, _end) {
              if (len === 32) { return x; }
              return (_end ? x|0 : x << (32-len)) + len * 0x10000000000;
            },

            /**
             * Get the number of bits used by a partial word.
             * @param {Number} x The partial word.
             * @return {Number} The number of bits used by the partial word.
             */
            getPartial: function (x) {
              return Math.round(x/0x10000000000) || 32;
            },

            /**
             * Compare two arrays for equality in a predictable amount of time.
             * @param {bitArray} a The first array.
             * @param {bitArray} b The second array.
             * @return {boolean} true if a == b; false otherwise.
             */
            equal: function (a, b) {
              if (sjcl.bitArray.bitLength(a) !== sjcl.bitArray.bitLength(b)) {
                return false;
              }
              var x = 0, i;
              for (i=0; i<a.length; i++) {
                x |= a[i]^b[i];
              }
              return (x === 0);
            },

            /** Shift an array right.
             * @param {bitArray} a The array to shift.
             * @param {Number} shift The number of bits to shift.
             * @param {Number} [carry=0] A byte to carry in
             * @param {bitArray} [out=[]] An array to prepend to the output.
             * @private
             */
            _shiftRight: function (a, shift, carry, out) {
              var i, last2=0, shift2;
              if (out === undefined) { out = []; }

              for (; shift >= 32; shift -= 32) {
                out.push(carry);
                carry = 0;
              }
              if (shift === 0) {
                return out.concat(a);
              }

              for (i=0; i<a.length; i++) {
                out.push(carry | a[i]>>>shift);
                carry = a[i] << (32-shift);
              }
              last2 = a.length ? a[a.length-1] : 0;
              shift2 = sjcl.bitArray.getPartial(last2);
              out.push(sjcl.bitArray.partial(shift+shift2 & 31, (shift + shift2 > 32) ? carry : out.pop(),1));
              return out;
            },

            /** xor a block of 4 words together.
             * @private
             */
            _xor4: function(x,y) {
              return [x[0]^y[0],x[1]^y[1],x[2]^y[2],x[3]^y[3]];
            }
          };
          /** @fileOverview Bit array codec implementations.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /** @namespace UTF-8 strings */
          sjcl.codec.utf8String = {
            /** Convert from a bitArray to a UTF-8 string. */
            fromBits: function (arr) {
              var out = "", bl = sjcl.bitArray.bitLength(arr), i, tmp;
              for (i=0; i<bl/8; i++) {
                if ((i&3) === 0) {
                  tmp = arr[i/4];
                }
                out += String.fromCharCode(tmp >>> 24);
                tmp <<= 8;
              }
              return decodeURIComponent(escape(out));
            },

            /** Convert from a UTF-8 string to a bitArray. */
            toBits: function (str) {
              str = unescape(encodeURIComponent(str));
              var out = [], i, tmp=0;
              for (i=0; i<str.length; i++) {
                tmp = tmp << 8 | str.charCodeAt(i);
                if ((i&3) === 3) {
                  out.push(tmp);
                  tmp = 0;
                }
              }
              if (i&3) {
                out.push(sjcl.bitArray.partial(8*(i&3), tmp));
              }
              return out;
            }
          };
          /** @fileOverview Bit array codec implementations.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /** @namespace Hexadecimal */
          sjcl.codec.hex = {
            /** Convert from a bitArray to a hex string. */
            fromBits: function (arr) {
              var out = "", i, x;
              for (i=0; i<arr.length; i++) {
                out += ((arr[i]|0)+0xF00000000000).toString(16).substr(4);
              }
              return out.substr(0, sjcl.bitArray.bitLength(arr)/4);//.replace(/(.{8})/g, "$1 ");
            },
            /** Convert from a hex string to a bitArray. */
            toBits: function (str) {
              var i, out=[], len;
              str = str.replace(/\s|0x/g, "");
              len = str.length;
              str = str + "00000000";
              for (i=0; i<str.length; i+=8) {
                out.push(parseInt(str.substr(i,8),16)^0);
              }
              return sjcl.bitArray.clamp(out, len*4);
            }
          };

          /** @fileOverview Bit array codec implementations.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /** @namespace Base64 encoding/decoding */
          sjcl.codec.base64 = {
            /** The base64 alphabet.
             * @private
             */
            _chars: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",

            /** Convert from a bitArray to a base64 string. */
            fromBits: function (arr, _noEquals, _url) {
              var out = "", i, bits=0, c = sjcl.codec.base64._chars, ta=0, bl = sjcl.bitArray.bitLength(arr);
              if (_url) c = c.substr(0,62) + '-_';
              for (i=0; out.length * 6 < bl; ) {
                out += c.charAt((ta ^ arr[i]>>>bits) >>> 26);
                if (bits < 6) {
                  ta = arr[i] << (6-bits);
                  bits += 26;
                  i++;
                } else {
                  ta <<= 6;
                  bits -= 6;
                }
              }
              while ((out.length & 3) && !_noEquals) { out += "="; }
              return out;
            },

            /** Convert from a base64 string to a bitArray */
            toBits: function(str, _url) {
              str = str.replace(/\s|=/g,'');
              var out = [], i, bits=0, c = sjcl.codec.base64._chars, ta=0, x;
              if (_url) c = c.substr(0,62) + '-_';
              for (i=0; i<str.length; i++) {
                x = c.indexOf(str.charAt(i));
                if (x < 0) {
                  throw new sjcl.exception.invalid("this isn't base64!");
                }
                if (bits > 26) {
                  bits -= 26;
                  out.push(ta ^ x>>>bits);
                  ta  = x << (32-bits);
                } else {
                  bits += 6;
                  ta ^= x << (32-bits);
                }
              }
              if (bits&56) {
                out.push(sjcl.bitArray.partial(bits&56, ta, 1));
              }
              return out;
            }
          };

          sjcl.codec.base64url = {
            fromBits: function (arr) { return sjcl.codec.base64.fromBits(arr,1,1); },
            toBits: function (str) { return sjcl.codec.base64.toBits(str,1); }
          };
          /** @fileOverview Bit array codec implementations.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /** @namespace Arrays of bytes */
          sjcl.codec.bytes = {
            /** Convert from a bitArray to an array of bytes. */
            fromBits: function (arr) {
              var out = [], bl = sjcl.bitArray.bitLength(arr), i, tmp;
              for (i=0; i<bl/8; i++) {
                if ((i&3) === 0) {
                  tmp = arr[i/4];
                }
                out.push(tmp >>> 24);
                tmp <<= 8;
              }
              return out;
            },
            /** Convert from an array of bytes to a bitArray. */
            toBits: function (bytes) {
              var out = [], i, tmp=0;
              for (i=0; i<bytes.length; i++) {
                tmp = tmp << 8 | bytes[i];
                if ((i&3) === 3) {
                  out.push(tmp);
                  tmp = 0;
                }
              }
              if (i&3) {
                out.push(sjcl.bitArray.partial(8*(i&3), tmp));
              }
              return out;
            }
          };
          /** @fileOverview Javascript SHA-256 implementation.
           *
           * An older version of this implementation is available in the public
           * domain, but this one is (c) Emily Stark, Mike Hamburg, Dan Boneh,
           * Stanford University 2008-2010 and BSD-licensed for liability
           * reasons.
           *
           * Special thanks to Aldo Cortesi for pointing out several bugs in
           * this code.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /**
           * Context for a SHA-256 operation in progress.
           * @constructor
           * @class Secure Hash Algorithm, 256 bits.
           */
          sjcl.hash.sha256 = function (hash) {
            if (!this._key[0]) { this._precompute(); }
            if (hash) {
              this._h = hash._h.slice(0);
              this._buffer = hash._buffer.slice(0);
              this._length = hash._length;
            } else {
              this.reset();
            }
          };

          /**
           * Hash a string or an array of words.
           * @static
           * @param {bitArray|String} data the data to hash.
           * @return {bitArray} The hash value, an array of 16 big-endian words.
           */
          sjcl.hash.sha256.hash = function (data) {
            return (new sjcl.hash.sha256()).update(data).finalize();
          };

          sjcl.hash.sha256.prototype = {
            /**
             * The hash's block size, in bits.
             * @constant
             */
            blockSize: 512,

            /**
             * Reset the hash state.
             * @return this
             */
            reset:function () {
              this._h = this._init.slice(0);
              this._buffer = [];
              this._length = 0;
              return this;
            },

            /**
             * Input several words to the hash.
             * @param {bitArray|String} data the data to hash.
             * @return this
             */
            update: function (data) {
              if (typeof data === "string") {
                data = sjcl.codec.utf8String.toBits(data);
              }
              var i, b = this._buffer = sjcl.bitArray.concat(this._buffer, data),
                  ol = this._length,
                  nl = this._length = ol + sjcl.bitArray.bitLength(data);
              for (i = 512+ol & -512; i <= nl; i+= 512) {
                this._block(b.splice(0,16));
              }
              return this;
            },

            /**
             * Complete hashing and output the hash value.
             * @return {bitArray} The hash value, an array of 8 big-endian words.
             */
            finalize:function () {
              var i, b = this._buffer, h = this._h;

              // Round out and push the buffer
              b = sjcl.bitArray.concat(b, [sjcl.bitArray.partial(1,1)]);

              // Round out the buffer to a multiple of 16 words, less the 2 length words.
              for (i = b.length + 2; i & 15; i++) {
                b.push(0);
              }

              // append the length
              b.push(Math.floor(this._length / 0x100000000));
              b.push(this._length | 0);

              while (b.length) {
                this._block(b.splice(0,16));
              }

              this.reset();
              return h;
            },

            /**
             * The SHA-256 initialization vector, to be precomputed.
             * @private
             */
            _init:[],
            /*
            _init:[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19],
            */

            /**
             * The SHA-256 hash key, to be precomputed.
             * @private
             */
            _key:[],
            /*
            _key:
              [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
               0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
               0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
               0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
               0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
               0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
               0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
               0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2],
            */


            /**
             * Function to precompute _init and _key.
             * @private
             */
            _precompute: function () {
              var i = 0, prime = 2, factor;

              function frac(x) { return (x-Math.floor(x)) * 0x100000000 | 0; }

              outer: for (; i<64; prime++) {
                for (factor=2; factor*factor <= prime; factor++) {
                  if (prime % factor === 0) {
                    // not a prime
                    continue outer;
                  }
                }

                if (i<8) {
                  this._init[i] = frac(Math.pow(prime, 1/2));
                }
                this._key[i] = frac(Math.pow(prime, 1/3));
                i++;
              }
            },

            /**
             * Perform one cycle of SHA-256.
             * @param {bitArray} words one block of words.
             * @private
             */
            _block:function (words) {
              var i, tmp, a, b,
                w = words.slice(0),
                h = this._h,
                k = this._key,
                h0 = h[0], h1 = h[1], h2 = h[2], h3 = h[3],
                h4 = h[4], h5 = h[5], h6 = h[6], h7 = h[7];

              /* Rationale for placement of |0 :
               * If a value can overflow is original 32 bits by a factor of more than a few
               * million (2^23 ish), there is a possibility that it might overflow the
               * 53-bit mantissa and lose precision.
               *
               * To avoid this, we clamp back to 32 bits by |'ing with 0 on any value that
               * propagates around the loop, and on the hash state h[].  I don't believe
               * that the clamps on h4 and on h0 are strictly necessary, but it's close
               * (for h4 anyway), and better safe than sorry.
               *
               * The clamps on h[] are necessary for the output to be correct even in the
               * common case and for short inputs.
               */
              for (i=0; i<64; i++) {
                // load up the input word for this round
                if (i<16) {
                  tmp = w[i];
                } else {
                  a   = w[(i+1 ) & 15];
                  b   = w[(i+14) & 15];
                  tmp = w[i&15] = ((a>>>7  ^ a>>>18 ^ a>>>3  ^ a<<25 ^ a<<14) +
                                   (b>>>17 ^ b>>>19 ^ b>>>10 ^ b<<15 ^ b<<13) +
                                   w[i&15] + w[(i+9) & 15]) | 0;
                }

                tmp = (tmp + h7 + (h4>>>6 ^ h4>>>11 ^ h4>>>25 ^ h4<<26 ^ h4<<21 ^ h4<<7) +  (h6 ^ h4&(h5^h6)) + k[i]); // | 0;

                // shift register
                h7 = h6; h6 = h5; h5 = h4;
                h4 = h3 + tmp | 0;
                h3 = h2; h2 = h1; h1 = h0;

                h0 = (tmp +  ((h1&h2) ^ (h3&(h1^h2))) + (h1>>>2 ^ h1>>>13 ^ h1>>>22 ^ h1<<30 ^ h1<<19 ^ h1<<10)) | 0;
              }

              h[0] = h[0]+h0 | 0;
              h[1] = h[1]+h1 | 0;
              h[2] = h[2]+h2 | 0;
              h[3] = h[3]+h3 | 0;
              h[4] = h[4]+h4 | 0;
              h[5] = h[5]+h5 | 0;
              h[6] = h[6]+h6 | 0;
              h[7] = h[7]+h7 | 0;
            }
          };


          /** @fileOverview Javascript SHA-512 implementation.
           *
           * This implementation was written for CryptoJS by Jeff Mott and adapted for
           * SJCL by Stefan Thomas.
           *
           * CryptoJS (c) 2009–2012 by Jeff Mott. All rights reserved.
           * Released with New BSD License
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           * @author Jeff Mott
           * @author Stefan Thomas
           */

          /**
           * Context for a SHA-512 operation in progress.
           * @constructor
           * @class Secure Hash Algorithm, 512 bits.
           */
          sjcl.hash.sha512 = function (hash) {
            if (!this._key[0]) { this._precompute(); }
            if (hash) {
              this._h = hash._h.slice(0);
              this._buffer = hash._buffer.slice(0);
              this._length = hash._length;
            } else {
              this.reset();
            }
          };

          /**
           * Hash a string or an array of words.
           * @static
           * @param {bitArray|String} data the data to hash.
           * @return {bitArray} The hash value, an array of 16 big-endian words.
           */
          sjcl.hash.sha512.hash = function (data) {
            return (new sjcl.hash.sha512()).update(data).finalize();
          };

          sjcl.hash.sha512.prototype = {
            /**
             * The hash's block size, in bits.
             * @constant
             */
            blockSize: 1024,

            /**
             * Reset the hash state.
             * @return this
             */
            reset:function () {
              this._h = this._init.slice(0);
              this._buffer = [];
              this._length = 0;
              return this;
            },

            /**
             * Input several words to the hash.
             * @param {bitArray|String} data the data to hash.
             * @return this
             */
            update: function (data) {
              if (typeof data === "string") {
                data = sjcl.codec.utf8String.toBits(data);
              }
              var i, b = this._buffer = sjcl.bitArray.concat(this._buffer, data),
                  ol = this._length,
                  nl = this._length = ol + sjcl.bitArray.bitLength(data);
              for (i = 1024+ol & -1024; i <= nl; i+= 1024) {
                this._block(b.splice(0,32));
              }
              return this;
            },

            /**
             * Complete hashing and output the hash value.
             * @return {bitArray} The hash value, an array of 16 big-endian words.
             */
            finalize:function () {
              var i, b = this._buffer, h = this._h;

              // Round out and push the buffer
              b = sjcl.bitArray.concat(b, [sjcl.bitArray.partial(1,1)]);

              // Round out the buffer to a multiple of 32 words, less the 4 length words.
              for (i = b.length + 4; i & 31; i++) {
                b.push(0);
              }

              // append the length
              b.push(0);
              b.push(0);
              b.push(Math.floor(this._length / 0x100000000));
              b.push(this._length | 0);

              while (b.length) {
                this._block(b.splice(0,32));
              }

              this.reset();
              return h;
            },

            /**
             * The SHA-512 initialization vector, to be precomputed.
             * @private
             */
            _init:[],

            /**
             * Least significant 24 bits of SHA512 initialization values.
             *
             * Javascript only has 53 bits of precision, so we compute the 40 most
             * significant bits and add the remaining 24 bits as constants.
             *
             * @private
             */
            _initr: [ 0xbcc908, 0xcaa73b, 0x94f82b, 0x1d36f1, 0xe682d1, 0x3e6c1f, 0x41bd6b, 0x7e2179 ],

            /*
            _init:
            [0x6a09e667, 0xf3bcc908, 0xbb67ae85, 0x84caa73b, 0x3c6ef372, 0xfe94f82b, 0xa54ff53a, 0x5f1d36f1,
             0x510e527f, 0xade682d1, 0x9b05688c, 0x2b3e6c1f, 0x1f83d9ab, 0xfb41bd6b, 0x5be0cd19, 0x137e2179],
            */

            /**
             * The SHA-512 hash key, to be precomputed.
             * @private
             */
            _key:[],

            /**
             * Least significant 24 bits of SHA512 key values.
             * @private
             */
            _keyr:
            [0x28ae22, 0xef65cd, 0x4d3b2f, 0x89dbbc, 0x48b538, 0x05d019, 0x194f9b, 0x6d8118,
             0x030242, 0x706fbe, 0xe4b28c, 0xffb4e2, 0x7b896f, 0x1696b1, 0xc71235, 0x692694,
             0xf14ad2, 0x4f25e3, 0x8cd5b5, 0xac9c65, 0x2b0275, 0xa6e483, 0x41fbd4, 0x1153b5,
             0x66dfab, 0xb43210, 0xfb213f, 0xef0ee4, 0xa88fc2, 0x0aa725, 0x03826f, 0x0e6e70,
             0xd22ffc, 0x26c926, 0xc42aed, 0x95b3df, 0xaf63de, 0x77b2a8, 0xedaee6, 0x82353b,
             0xf10364, 0x423001, 0xf89791, 0x54be30, 0xef5218, 0x65a910, 0x71202a, 0xbbd1b8,
             0xd2d0c8, 0x41ab53, 0x8eeb99, 0x9b48a8, 0xc95a63, 0x418acb, 0x63e373, 0xb2b8a3,
             0xefb2fc, 0x172f60, 0xf0ab72, 0x6439ec, 0x631e28, 0x82bde9, 0xc67915, 0x72532b,
             0x26619c, 0xc0c207, 0xe0eb1e, 0x6ed178, 0x176fba, 0xc898a6, 0xf90dae, 0x1c471b,
             0x047d84, 0xc72493, 0xc9bebc, 0x100d4c, 0x3e42b6, 0x657e2a, 0xd6faec, 0x475817],

            /*
            _key:
            [0x428a2f98, 0xd728ae22, 0x71374491, 0x23ef65cd, 0xb5c0fbcf, 0xec4d3b2f, 0xe9b5dba5, 0x8189dbbc,
             0x3956c25b, 0xf348b538, 0x59f111f1, 0xb605d019, 0x923f82a4, 0xaf194f9b, 0xab1c5ed5, 0xda6d8118,
             0xd807aa98, 0xa3030242, 0x12835b01, 0x45706fbe, 0x243185be, 0x4ee4b28c, 0x550c7dc3, 0xd5ffb4e2,
             0x72be5d74, 0xf27b896f, 0x80deb1fe, 0x3b1696b1, 0x9bdc06a7, 0x25c71235, 0xc19bf174, 0xcf692694,
             0xe49b69c1, 0x9ef14ad2, 0xefbe4786, 0x384f25e3, 0x0fc19dc6, 0x8b8cd5b5, 0x240ca1cc, 0x77ac9c65,
             0x2de92c6f, 0x592b0275, 0x4a7484aa, 0x6ea6e483, 0x5cb0a9dc, 0xbd41fbd4, 0x76f988da, 0x831153b5,
             0x983e5152, 0xee66dfab, 0xa831c66d, 0x2db43210, 0xb00327c8, 0x98fb213f, 0xbf597fc7, 0xbeef0ee4,
             0xc6e00bf3, 0x3da88fc2, 0xd5a79147, 0x930aa725, 0x06ca6351, 0xe003826f, 0x14292967, 0x0a0e6e70,
             0x27b70a85, 0x46d22ffc, 0x2e1b2138, 0x5c26c926, 0x4d2c6dfc, 0x5ac42aed, 0x53380d13, 0x9d95b3df,
             0x650a7354, 0x8baf63de, 0x766a0abb, 0x3c77b2a8, 0x81c2c92e, 0x47edaee6, 0x92722c85, 0x1482353b,
             0xa2bfe8a1, 0x4cf10364, 0xa81a664b, 0xbc423001, 0xc24b8b70, 0xd0f89791, 0xc76c51a3, 0x0654be30,
             0xd192e819, 0xd6ef5218, 0xd6990624, 0x5565a910, 0xf40e3585, 0x5771202a, 0x106aa070, 0x32bbd1b8,
             0x19a4c116, 0xb8d2d0c8, 0x1e376c08, 0x5141ab53, 0x2748774c, 0xdf8eeb99, 0x34b0bcb5, 0xe19b48a8,
             0x391c0cb3, 0xc5c95a63, 0x4ed8aa4a, 0xe3418acb, 0x5b9cca4f, 0x7763e373, 0x682e6ff3, 0xd6b2b8a3,
             0x748f82ee, 0x5defb2fc, 0x78a5636f, 0x43172f60, 0x84c87814, 0xa1f0ab72, 0x8cc70208, 0x1a6439ec,
             0x90befffa, 0x23631e28, 0xa4506ceb, 0xde82bde9, 0xbef9a3f7, 0xb2c67915, 0xc67178f2, 0xe372532b,
             0xca273ece, 0xea26619c, 0xd186b8c7, 0x21c0c207, 0xeada7dd6, 0xcde0eb1e, 0xf57d4f7f, 0xee6ed178,
             0x06f067aa, 0x72176fba, 0x0a637dc5, 0xa2c898a6, 0x113f9804, 0xbef90dae, 0x1b710b35, 0x131c471b,
             0x28db77f5, 0x23047d84, 0x32caab7b, 0x40c72493, 0x3c9ebe0a, 0x15c9bebc, 0x431d67c4, 0x9c100d4c,
             0x4cc5d4be, 0xcb3e42b6, 0x597f299c, 0xfc657e2a, 0x5fcb6fab, 0x3ad6faec, 0x6c44198c, 0x4a475817],
            */

            /**
             * Function to precompute _init and _key.
             * @private
             */
            _precompute: function () {
              // XXX: This code is for precomputing the SHA256 constants, change for
              //      SHA512 and re-enable.
              var i = 0, prime = 2, factor;

              function frac(x)  { return (x-Math.floor(x)) * 0x100000000 | 0; }
              function frac2(x) { return (x-Math.floor(x)) * 0x10000000000 & 0xff; }

              outer: for (; i<80; prime++) {
                for (factor=2; factor*factor <= prime; factor++) {
                  if (prime % factor === 0) {
                    // not a prime
                    continue outer;
                  }
                }

                if (i<8) {
                  this._init[i*2] = frac(Math.pow(prime, 1/2));
                  this._init[i*2+1] = (frac2(Math.pow(prime, 1/2)) << 24) | this._initr[i];
                }
                this._key[i*2] = frac(Math.pow(prime, 1/3));
                this._key[i*2+1] = (frac2(Math.pow(prime, 1/3)) << 24) | this._keyr[i];
                i++;
              }
            },

            /**
             * Perform one cycle of SHA-512.
             * @param {bitArray} words one block of words.
             * @private
             */
            _block:function (words) {
              var i, wrh, wrl,
                  w = words.slice(0),
                  h = this._h,
                  k = this._key,
                  h0h = h[ 0], h0l = h[ 1], h1h = h[ 2], h1l = h[ 3],
                  h2h = h[ 4], h2l = h[ 5], h3h = h[ 6], h3l = h[ 7],
                  h4h = h[ 8], h4l = h[ 9], h5h = h[10], h5l = h[11],
                  h6h = h[12], h6l = h[13], h7h = h[14], h7l = h[15];

              // Working variables
              var ah = h0h, al = h0l, bh = h1h, bl = h1l,
                  ch = h2h, cl = h2l, dh = h3h, dl = h3l,
                  eh = h4h, el = h4l, fh = h5h, fl = h5l,
                  gh = h6h, gl = h6l, hh = h7h, hl = h7l;

              for (i=0; i<80; i++) {
                // load up the input word for this round
                if (i<16) {
                  wrh = w[i * 2];
                  wrl = w[i * 2 + 1];
                } else {
                  // Gamma0
                  var gamma0xh = w[(i-15) * 2];
                  var gamma0xl = w[(i-15) * 2 + 1];
                  var gamma0h =
                    ((gamma0xl << 31) | (gamma0xh >>> 1)) ^
                    ((gamma0xl << 24) | (gamma0xh >>> 8)) ^
                     (gamma0xh >>> 7);
                  var gamma0l =
                    ((gamma0xh << 31) | (gamma0xl >>> 1)) ^
                    ((gamma0xh << 24) | (gamma0xl >>> 8)) ^
                    ((gamma0xh << 25) | (gamma0xl >>> 7));

                  // Gamma1
                  var gamma1xh = w[(i-2) * 2];
                  var gamma1xl = w[(i-2) * 2 + 1];
                  var gamma1h =
                    ((gamma1xl << 13) | (gamma1xh >>> 19)) ^
                    ((gamma1xh << 3)  | (gamma1xl >>> 29)) ^
                     (gamma1xh >>> 6);
                  var gamma1l =
                    ((gamma1xh << 13) | (gamma1xl >>> 19)) ^
                    ((gamma1xl << 3)  | (gamma1xh >>> 29)) ^
                    ((gamma1xh << 26) | (gamma1xl >>> 6));

                  // Shortcuts
                  var wr7h = w[(i-7) * 2];
                  var wr7l = w[(i-7) * 2 + 1];

                  var wr16h = w[(i-16) * 2];
                  var wr16l = w[(i-16) * 2 + 1];

                  // W(round) = gamma0 + W(round - 7) + gamma1 + W(round - 16)
                  wrl = gamma0l + wr7l;
                  wrh = gamma0h + wr7h + ((wrl >>> 0) < (gamma0l >>> 0) ? 1 : 0);
                  wrl += gamma1l;
                  wrh += gamma1h + ((wrl >>> 0) < (gamma1l >>> 0) ? 1 : 0);
                  wrl += wr16l;
                  wrh += wr16h + ((wrl >>> 0) < (wr16l >>> 0) ? 1 : 0);
                }

                w[i*2]     = wrh |= 0;
                w[i*2 + 1] = wrl |= 0;

                // Ch
                var chh = (eh & fh) ^ (~eh & gh);
                var chl = (el & fl) ^ (~el & gl);

                // Maj
                var majh = (ah & bh) ^ (ah & ch) ^ (bh & ch);
                var majl = (al & bl) ^ (al & cl) ^ (bl & cl);

                // Sigma0
                var sigma0h = ((al << 4) | (ah >>> 28)) ^ ((ah << 30) | (al >>> 2)) ^ ((ah << 25) | (al >>> 7));
                var sigma0l = ((ah << 4) | (al >>> 28)) ^ ((al << 30) | (ah >>> 2)) ^ ((al << 25) | (ah >>> 7));

                // Sigma1
                var sigma1h = ((el << 18) | (eh >>> 14)) ^ ((el << 14) | (eh >>> 18)) ^ ((eh << 23) | (el >>> 9));
                var sigma1l = ((eh << 18) | (el >>> 14)) ^ ((eh << 14) | (el >>> 18)) ^ ((el << 23) | (eh >>> 9));

                // K(round)
                var krh = k[i*2];
                var krl = k[i*2+1];

                // t1 = h + sigma1 + ch + K(round) + W(round)
                var t1l = hl + sigma1l;
                var t1h = hh + sigma1h + ((t1l >>> 0) < (hl >>> 0) ? 1 : 0);
                t1l += chl;
                t1h += chh + ((t1l >>> 0) < (chl >>> 0) ? 1 : 0);
                t1l += krl;
                t1h += krh + ((t1l >>> 0) < (krl >>> 0) ? 1 : 0);
                t1l += wrl;
                t1h += wrh + ((t1l >>> 0) < (wrl >>> 0) ? 1 : 0);

                // t2 = sigma0 + maj
                var t2l = sigma0l + majl;
                var t2h = sigma0h + majh + ((t2l >>> 0) < (sigma0l >>> 0) ? 1 : 0);

                // Update working variables
                hh = gh;
                hl = gl;
                gh = fh;
                gl = fl;
                fh = eh;
                fl = el;
                el = (dl + t1l) | 0;
                eh = (dh + t1h + ((el >>> 0) < (dl >>> 0) ? 1 : 0)) | 0;
                dh = ch;
                dl = cl;
                ch = bh;
                cl = bl;
                bh = ah;
                bl = al;
                al = (t1l + t2l) | 0;
                ah = (t1h + t2h + ((al >>> 0) < (t1l >>> 0) ? 1 : 0)) | 0;
              }

              // Intermediate hash
              h0l = h[1] = (h0l + al) | 0;
              h[0] = (h0h + ah + ((h0l >>> 0) < (al >>> 0) ? 1 : 0)) | 0;
              h1l = h[3] = (h1l + bl) | 0;
              h[2] = (h1h + bh + ((h1l >>> 0) < (bl >>> 0) ? 1 : 0)) | 0;
              h2l = h[5] = (h2l + cl) | 0;
              h[4] = (h2h + ch + ((h2l >>> 0) < (cl >>> 0) ? 1 : 0)) | 0;
              h3l = h[7] = (h3l + dl) | 0;
              h[6] = (h3h + dh + ((h3l >>> 0) < (dl >>> 0) ? 1 : 0)) | 0;
              h4l = h[9] = (h4l + el) | 0;
              h[8] = (h4h + eh + ((h4l >>> 0) < (el >>> 0) ? 1 : 0)) | 0;
              h5l = h[11] = (h5l + fl) | 0;
              h[10] = (h5h + fh + ((h5l >>> 0) < (fl >>> 0) ? 1 : 0)) | 0;
              h6l = h[13] = (h6l + gl) | 0;
              h[12] = (h6h + gh + ((h6l >>> 0) < (gl >>> 0) ? 1 : 0)) | 0;
              h7l = h[15] = (h7l + hl) | 0;
              h[14] = (h7h + hh + ((h7l >>> 0) < (hl >>> 0) ? 1 : 0)) | 0;
            }
          };


          /** @fileOverview CCM mode implementation.
           *
           * Special thanks to Roy Nicholson for pointing out a bug in our
           * implementation.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /** @namespace CTR mode with CBC MAC. */
          sjcl.mode.ccm = {
            /** The name of the mode.
             * @constant
             */
            name: "ccm",

            /** Encrypt in CCM mode.
             * @static
             * @param {Object} prf The pseudorandom function.  It must have a block size of 16 bytes.
             * @param {bitArray} plaintext The plaintext data.
             * @param {bitArray} iv The initialization value.
             * @param {bitArray} [adata=[]] The authenticated data.
             * @param {Number} [tlen=64] the desired tag length, in bits.
             * @return {bitArray} The encrypted data, an array of bytes.
             */
            encrypt: function(prf, plaintext, iv, adata, tlen) {
              var L, i, out = plaintext.slice(0), tag, w=sjcl.bitArray, ivl = w.bitLength(iv) / 8, ol = w.bitLength(out) / 8;
              tlen = tlen || 64;
              adata = adata || [];

              if (ivl < 7) {
                throw new sjcl.exception.invalid("ccm: iv must be at least 7 bytes");
              }

              // compute the length of the length
              for (L=2; L<4 && ol >>> 8*L; L++) {}
              if (L < 15 - ivl) { L = 15-ivl; }
              iv = w.clamp(iv,8*(15-L));

              // compute the tag
              tag = sjcl.mode.ccm._computeTag(prf, plaintext, iv, adata, tlen, L);

              // encrypt
              out = sjcl.mode.ccm._ctrMode(prf, out, iv, tag, tlen, L);

              return w.concat(out.data, out.tag);
            },

            /** Decrypt in CCM mode.
             * @static
             * @param {Object} prf The pseudorandom function.  It must have a block size of 16 bytes.
             * @param {bitArray} ciphertext The ciphertext data.
             * @param {bitArray} iv The initialization value.
             * @param {bitArray} [[]] adata The authenticated data.
             * @param {Number} [64] tlen the desired tag length, in bits.
             * @return {bitArray} The decrypted data.
             */
            decrypt: function(prf, ciphertext, iv, adata, tlen) {
              tlen = tlen || 64;
              adata = adata || [];
              var L, i,
                  w=sjcl.bitArray,
                  ivl = w.bitLength(iv) / 8,
                  ol = w.bitLength(ciphertext),
                  out = w.clamp(ciphertext, ol - tlen),
                  tag = w.bitSlice(ciphertext, ol - tlen), tag2;


              ol = (ol - tlen) / 8;

              if (ivl < 7) {
                throw new sjcl.exception.invalid("ccm: iv must be at least 7 bytes");
              }

              // compute the length of the length
              for (L=2; L<4 && ol >>> 8*L; L++) {}
              if (L < 15 - ivl) { L = 15-ivl; }
              iv = w.clamp(iv,8*(15-L));

              // decrypt
              out = sjcl.mode.ccm._ctrMode(prf, out, iv, tag, tlen, L);

              // check the tag
              tag2 = sjcl.mode.ccm._computeTag(prf, out.data, iv, adata, tlen, L);
              if (!w.equal(out.tag, tag2)) {
                throw new sjcl.exception.corrupt("ccm: tag doesn't match");
              }

              return out.data;
            },

            /* Compute the (unencrypted) authentication tag, according to the CCM specification
             * @param {Object} prf The pseudorandom function.
             * @param {bitArray} plaintext The plaintext data.
             * @param {bitArray} iv The initialization value.
             * @param {bitArray} adata The authenticated data.
             * @param {Number} tlen the desired tag length, in bits.
             * @return {bitArray} The tag, but not yet encrypted.
             * @private
             */
            _computeTag: function(prf, plaintext, iv, adata, tlen, L) {
              // compute B[0]
              var q, mac, field = 0, offset = 24, tmp, i, macData = [], w=sjcl.bitArray, xor = w._xor4;

              tlen /= 8;

              // check tag length and message length
              if (tlen % 2 || tlen < 4 || tlen > 16) {
                throw new sjcl.exception.invalid("ccm: invalid tag length");
              }

              if (adata.length > 0xFFFFFFFF || plaintext.length > 0xFFFFFFFF) {
                // I don't want to deal with extracting high words from doubles.
                throw new sjcl.exception.bug("ccm: can't deal with 4GiB or more data");
              }

              // mac the flags
              mac = [w.partial(8, (adata.length ? 1<<6 : 0) | (tlen-2) << 2 | L-1)];

              // mac the iv and length
              mac = w.concat(mac, iv);
              mac[3] |= w.bitLength(plaintext)/8;
              mac = prf.encrypt(mac);


              if (adata.length) {
                // mac the associated data.  start with its length...
                tmp = w.bitLength(adata)/8;
                if (tmp <= 0xFEFF) {
                  macData = [w.partial(16, tmp)];
                } else if (tmp <= 0xFFFFFFFF) {
                  macData = w.concat([w.partial(16,0xFFFE)], [tmp]);
                } // else ...

                // mac the data itself
                macData = w.concat(macData, adata);
                for (i=0; i<macData.length; i += 4) {
                  mac = prf.encrypt(xor(mac, macData.slice(i,i+4).concat([0,0,0])));
                }
              }

              // mac the plaintext
              for (i=0; i<plaintext.length; i+=4) {
                mac = prf.encrypt(xor(mac, plaintext.slice(i,i+4).concat([0,0,0])));
              }

              return w.clamp(mac, tlen * 8);
            },

            /** CCM CTR mode.
             * Encrypt or decrypt data and tag with the prf in CCM-style CTR mode.
             * May mutate its arguments.
             * @param {Object} prf The PRF.
             * @param {bitArray} data The data to be encrypted or decrypted.
             * @param {bitArray} iv The initialization vector.
             * @param {bitArray} tag The authentication tag.
             * @param {Number} tlen The length of th etag, in bits.
             * @param {Number} L The CCM L value.
             * @return {Object} An object with data and tag, the en/decryption of data and tag values.
             * @private
             */
            _ctrMode: function(prf, data, iv, tag, tlen, L) {
              var enc, i, w=sjcl.bitArray, xor = w._xor4, ctr, b, l = data.length, bl=w.bitLength(data);

              // start the ctr
              ctr = w.concat([w.partial(8,L-1)],iv).concat([0,0,0]).slice(0,4);

              // en/decrypt the tag
              tag = w.bitSlice(xor(tag,prf.encrypt(ctr)), 0, tlen);

              // en/decrypt the data
              if (!l) { return {tag:tag, data:[]}; }

              for (i=0; i<l; i+=4) {
                ctr[3]++;
                enc = prf.encrypt(ctr);
                data[i]   ^= enc[0];
                data[i+1] ^= enc[1];
                data[i+2] ^= enc[2];
                data[i+3] ^= enc[3];
              }
              return { tag:tag, data:w.clamp(data,bl) };
            }
          };
          /** @fileOverview CBC mode implementation
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /** @namespace
           * Dangerous: CBC mode with PKCS#5 padding.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */
          if (sjcl.beware === undefined) {
            sjcl.beware = {};
          }
          sjcl.beware["CBC mode is dangerous because it doesn't protect message integrity."
          ] = function() {
            sjcl.mode.cbc = {
              /** The name of the mode.
               * @constant
               */
              name: "cbc",

              /** Encrypt in CBC mode with PKCS#5 padding.
               * @param {Object} prp The block cipher.  It must have a block size of 16 bytes.
               * @param {bitArray} plaintext The plaintext data.
               * @param {bitArray} iv The initialization value.
               * @param {bitArray} [adata=[]] The authenticated data.  Must be empty.
               * @return The encrypted data, an array of bytes.
               * @throws {sjcl.exception.invalid} if the IV isn't exactly 128 bits, or if any adata is specified.
               */
              encrypt: function(prp, plaintext, iv, adata) {
                if (adata && adata.length) {
                  throw new sjcl.exception.invalid("cbc can't authenticate data");
                }
                if (sjcl.bitArray.bitLength(iv) !== 128) {
                  throw new sjcl.exception.invalid("cbc iv must be 128 bits");
                }
                var i,
                    w = sjcl.bitArray,
                    xor = w._xor4,
                    bl = w.bitLength(plaintext),
                    bp = 0,
                    output = [];

                if (bl&7) {
                  throw new sjcl.exception.invalid("pkcs#5 padding only works for multiples of a byte");
                }

                for (i=0; bp+128 <= bl; i+=4, bp+=128) {
                  /* Encrypt a non-final block */
                  iv = prp.encrypt(xor(iv, plaintext.slice(i,i+4)));
                  output.splice(i,0,iv[0],iv[1],iv[2],iv[3]);
                }

                /* Construct the pad. */
                bl = (16 - ((bl >> 3) & 15)) * 0x1010101;

                /* Pad and encrypt. */
                iv = prp.encrypt(xor(iv,w.concat(plaintext,[bl,bl,bl,bl]).slice(i,i+4)));
                output.splice(i,0,iv[0],iv[1],iv[2],iv[3]);
                return output;
              },

              /** Decrypt in CBC mode.
               * @param {Object} prp The block cipher.  It must have a block size of 16 bytes.
               * @param {bitArray} ciphertext The ciphertext data.
               * @param {bitArray} iv The initialization value.
               * @param {bitArray} [adata=[]] The authenticated data.  It must be empty.
               * @return The decrypted data, an array of bytes.
               * @throws {sjcl.exception.invalid} if the IV isn't exactly 128 bits, or if any adata is specified.
               * @throws {sjcl.exception.corrupt} if if the message is corrupt.
               */
              decrypt: function(prp, ciphertext, iv, adata) {
                if (adata && adata.length) {
                  throw new sjcl.exception.invalid("cbc can't authenticate data");
                }
                if (sjcl.bitArray.bitLength(iv) !== 128) {
                  throw new sjcl.exception.invalid("cbc iv must be 128 bits");
                }
                if ((sjcl.bitArray.bitLength(ciphertext) & 127) || !ciphertext.length) {
                  throw new sjcl.exception.corrupt("cbc ciphertext must be a positive multiple of the block size");
                }
                var i,
                    w = sjcl.bitArray,
                    xor = w._xor4,
                    bi, bo,
                    output = [];

                adata = adata || [];

                for (i=0; i<ciphertext.length; i+=4) {
                  bi = ciphertext.slice(i,i+4);
                  bo = xor(iv,prp.decrypt(bi));
                  output.splice(i,0,bo[0],bo[1],bo[2],bo[3]);
                  iv = bi;
                }
                // return w.bitSlice(output, 0, output.length*32);;

                /* check and remove the pad */
                bi = output[i-1] & 255;
                if (bi == 0 || bi > 16) {
                  throw new sjcl.exception.corrupt("pkcs#5 padding corrupt");
                }
                bo = bi * 0x1010101;
                if (!w.equal(w.bitSlice([bo,bo,bo,bo], 0, bi*8),
                             w.bitSlice(output, output.length*32 - bi*8, output.length*32))) {
                  throw new sjcl.exception.corrupt("pkcs#5 padding corrupt");
                }

                return w.bitSlice(output, 0, output.length*32 - bi*8);
              }
            };
          };
          /** @fileOverview OCB 2.0 implementation
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /** @namespace
           * Phil Rogaway's Offset CodeBook mode, version 2.0.
           * May be covered by US and international patents.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */
          sjcl.mode.ocb2 = {
            /** The name of the mode.
             * @constant
             */
            name: "ocb2",

            /** Encrypt in OCB mode, version 2.0.
             * @param {Object} prp The block cipher.  It must have a block size of 16 bytes.
             * @param {bitArray} plaintext The plaintext data.
             * @param {bitArray} iv The initialization value.
             * @param {bitArray} [adata=[]] The authenticated data.
             * @param {Number} [tlen=64] the desired tag length, in bits.
             * @param [false] premac 1 if the authentication data is pre-macced with PMAC.
             * @return The encrypted data, an array of bytes.
             * @throws {sjcl.exception.invalid} if the IV isn't exactly 128 bits.
             */
            encrypt: function(prp, plaintext, iv, adata, tlen, premac) {
              if (sjcl.bitArray.bitLength(iv) !== 128) {
                throw new sjcl.exception.invalid("ocb iv must be 128 bits");
              }
              var i,
                  times2 = sjcl.mode.ocb2._times2,
                  w = sjcl.bitArray,
                  xor = w._xor4,
                  checksum = [0,0,0,0],
                  delta = times2(prp.encrypt(iv)),
                  bi, bl,
                  output = [],
                  pad;

              adata = adata || [];
              tlen  = tlen || 64;

              for (i=0; i+4 < plaintext.length; i+=4) {
                /* Encrypt a non-final block */
                bi = plaintext.slice(i,i+4);
                checksum = xor(checksum, bi);
                output = output.concat(xor(delta,prp.encrypt(xor(delta, bi))));
                delta = times2(delta);
              }

              /* Chop out the final block */
              bi = plaintext.slice(i);
              bl = w.bitLength(bi);
              pad = prp.encrypt(xor(delta,[0,0,0,bl]));
              bi = w.clamp(xor(bi.concat([0,0,0]),pad), bl);

              /* Checksum the final block, and finalize the checksum */
              checksum = xor(checksum,xor(bi.concat([0,0,0]),pad));
              checksum = prp.encrypt(xor(checksum,xor(delta,times2(delta))));

              /* MAC the header */
              if (adata.length) {
                checksum = xor(checksum, premac ? adata : sjcl.mode.ocb2.pmac(prp, adata));
              }

              return output.concat(w.concat(bi, w.clamp(checksum, tlen)));
            },

            /** Decrypt in OCB mode.
             * @param {Object} prp The block cipher.  It must have a block size of 16 bytes.
             * @param {bitArray} ciphertext The ciphertext data.
             * @param {bitArray} iv The initialization value.
             * @param {bitArray} [adata=[]] The authenticated data.
             * @param {Number} [tlen=64] the desired tag length, in bits.
             * @param {boolean} [premac=false] true if the authentication data is pre-macced with PMAC.
             * @return The decrypted data, an array of bytes.
             * @throws {sjcl.exception.invalid} if the IV isn't exactly 128 bits.
             * @throws {sjcl.exception.corrupt} if if the message is corrupt.
             */
            decrypt: function(prp, ciphertext, iv, adata, tlen, premac) {
              if (sjcl.bitArray.bitLength(iv) !== 128) {
                throw new sjcl.exception.invalid("ocb iv must be 128 bits");
              }
              tlen  = tlen || 64;
              var i,
                  times2 = sjcl.mode.ocb2._times2,
                  w = sjcl.bitArray,
                  xor = w._xor4,
                  checksum = [0,0,0,0],
                  delta = times2(prp.encrypt(iv)),
                  bi, bl,
                  len = sjcl.bitArray.bitLength(ciphertext) - tlen,
                  output = [],
                  pad;

              adata = adata || [];

              for (i=0; i+4 < len/32; i+=4) {
                /* Decrypt a non-final block */
                bi = xor(delta, prp.decrypt(xor(delta, ciphertext.slice(i,i+4))));
                checksum = xor(checksum, bi);
                output = output.concat(bi);
                delta = times2(delta);
              }

              /* Chop out and decrypt the final block */
              bl = len-i*32;
              pad = prp.encrypt(xor(delta,[0,0,0,bl]));
              bi = xor(pad, w.clamp(ciphertext.slice(i),bl).concat([0,0,0]));

              /* Checksum the final block, and finalize the checksum */
              checksum = xor(checksum, bi);
              checksum = prp.encrypt(xor(checksum, xor(delta, times2(delta))));

              /* MAC the header */
              if (adata.length) {
                checksum = xor(checksum, premac ? adata : sjcl.mode.ocb2.pmac(prp, adata));
              }

              if (!w.equal(w.clamp(checksum, tlen), w.bitSlice(ciphertext, len))) {
                throw new sjcl.exception.corrupt("ocb: tag doesn't match");
              }

              return output.concat(w.clamp(bi,bl));
            },

            /** PMAC authentication for OCB associated data.
             * @param {Object} prp The block cipher.  It must have a block size of 16 bytes.
             * @param {bitArray} adata The authenticated data.
             */
            pmac: function(prp, adata) {
              var i,
                  times2 = sjcl.mode.ocb2._times2,
                  w = sjcl.bitArray,
                  xor = w._xor4,
                  checksum = [0,0,0,0],
                  delta = prp.encrypt([0,0,0,0]),
                  bi;

              delta = xor(delta,times2(times2(delta)));

              for (i=0; i+4<adata.length; i+=4) {
                delta = times2(delta);
                checksum = xor(checksum, prp.encrypt(xor(delta, adata.slice(i,i+4))));
              }

              bi = adata.slice(i);
              if (w.bitLength(bi) < 128) {
                delta = xor(delta,times2(delta));
                bi = w.concat(bi,[0x80000000|0,0,0,0]);
              }
              checksum = xor(checksum, bi);
              return prp.encrypt(xor(times2(xor(delta,times2(delta))), checksum));
            },

            /** Double a block of words, OCB style.
             * @private
             */
            _times2: function(x) {
              return [x[0]<<1 ^ x[1]>>>31,
                      x[1]<<1 ^ x[2]>>>31,
                      x[2]<<1 ^ x[3]>>>31,
                      x[3]<<1 ^ (x[0]>>>31)*0x87];
            }
          };
          /** @fileOverview GCM mode implementation.
           *
           * @author Juho Vähä-Herttua
           */

          /** @namespace Galois/Counter mode. */
          sjcl.mode.gcm = {
            /** The name of the mode.
             * @constant
             */
            name: "gcm",

            /** Encrypt in GCM mode.
             * @static
             * @param {Object} prf The pseudorandom function.  It must have a block size of 16 bytes.
             * @param {bitArray} plaintext The plaintext data.
             * @param {bitArray} iv The initialization value.
             * @param {bitArray} [adata=[]] The authenticated data.
             * @param {Number} [tlen=128] The desired tag length, in bits.
             * @return {bitArray} The encrypted data, an array of bytes.
             */
            encrypt: function (prf, plaintext, iv, adata, tlen) {
              var out, data = plaintext.slice(0), w=sjcl.bitArray;
              tlen = tlen || 128;
              adata = adata || [];

              // encrypt and tag
              out = sjcl.mode.gcm._ctrMode(true, prf, data, adata, iv, tlen);

              return w.concat(out.data, out.tag);
            },

            /** Decrypt in GCM mode.
             * @static
             * @param {Object} prf The pseudorandom function.  It must have a block size of 16 bytes.
             * @param {bitArray} ciphertext The ciphertext data.
             * @param {bitArray} iv The initialization value.
             * @param {bitArray} [adata=[]] The authenticated data.
             * @param {Number} [tlen=128] The desired tag length, in bits.
             * @return {bitArray} The decrypted data.
             */
            decrypt: function (prf, ciphertext, iv, adata, tlen) {
              var out, data = ciphertext.slice(0), tag, w=sjcl.bitArray, l=w.bitLength(data);
              tlen = tlen || 128;
              adata = adata || [];

              // Slice tag out of data
              if (tlen <= l) {
                tag = w.bitSlice(data, l-tlen);
                data = w.bitSlice(data, 0, l-tlen);
              } else {
                tag = data;
                data = [];
              }

              // decrypt and tag
              out = sjcl.mode.gcm._ctrMode(false, prf, data, adata, iv, tlen);

              if (!w.equal(out.tag, tag)) {
                throw new sjcl.exception.corrupt("gcm: tag doesn't match");
              }
              return out.data;
            },

            /* Compute the galois multiplication of X and Y
             * @private
             */
            _galoisMultiply: function (x, y) {
              var i, j, xi, Zi, Vi, lsb_Vi, w=sjcl.bitArray, xor=w._xor4;

              Zi = [0,0,0,0];
              Vi = y.slice(0);

              // Block size is 128 bits, run 128 times to get Z_128
              for (i=0; i<128; i++) {
                xi = (x[Math.floor(i/32)] & (1 << (31-i%32))) !== 0;
                if (xi) {
                  // Z_i+1 = Z_i ^ V_i
                  Zi = xor(Zi, Vi);
                }

                // Store the value of LSB(V_i)
                lsb_Vi = (Vi[3] & 1) !== 0;

                // V_i+1 = V_i >> 1
                for (j=3; j>0; j--) {
                  Vi[j] = (Vi[j] >>> 1) | ((Vi[j-1]&1) << 31);
                }
                Vi[0] = Vi[0] >>> 1;

                // If LSB(V_i) is 1, V_i+1 = (V_i >> 1) ^ R
                if (lsb_Vi) {
                  Vi[0] = Vi[0] ^ (0xe1 << 24);
                }
              }
              return Zi;
            },

            _ghash: function(H, Y0, data) {
              var Yi, i, l = data.length;

              Yi = Y0.slice(0);
              for (i=0; i<l; i+=4) {
                Yi[0] ^= 0xffffffff&data[i];
                Yi[1] ^= 0xffffffff&data[i+1];
                Yi[2] ^= 0xffffffff&data[i+2];
                Yi[3] ^= 0xffffffff&data[i+3];
                Yi = sjcl.mode.gcm._galoisMultiply(Yi, H);
              }
              return Yi;
            },

            /** GCM CTR mode.
             * Encrypt or decrypt data and tag with the prf in GCM-style CTR mode.
             * @param {Boolean} encrypt True if encrypt, false if decrypt.
             * @param {Object} prf The PRF.
             * @param {bitArray} data The data to be encrypted or decrypted.
             * @param {bitArray} iv The initialization vector.
             * @param {bitArray} adata The associated data to be tagged.
             * @param {Number} tlen The length of the tag, in bits.
             */
            _ctrMode: function(encrypt, prf, data, adata, iv, tlen) {
              var H, J0, S0, enc, i, ctr, tag, last, l, bl, abl, ivbl, w=sjcl.bitArray, xor=w._xor4;

              // Calculate data lengths
              l = data.length;
              bl = w.bitLength(data);
              abl = w.bitLength(adata);
              ivbl = w.bitLength(iv);

              // Calculate the parameters
              H = prf.encrypt([0,0,0,0]);
              if (ivbl === 96) {
                J0 = iv.slice(0);
                J0 = w.concat(J0, [1]);
              } else {
                J0 = sjcl.mode.gcm._ghash(H, [0,0,0,0], iv);
                J0 = sjcl.mode.gcm._ghash(H, J0, [0,0,Math.floor(ivbl/0x100000000),ivbl&0xffffffff]);
              }
              S0 = sjcl.mode.gcm._ghash(H, [0,0,0,0], adata);

              // Initialize ctr and tag
              ctr = J0.slice(0);
              tag = S0.slice(0);

              // If decrypting, calculate hash
              if (!encrypt) {
                tag = sjcl.mode.gcm._ghash(H, S0, data);
              }

              // Encrypt all the data
              for (i=0; i<l; i+=4) {
                 ctr[3]++;
                 enc = prf.encrypt(ctr);
                 data[i]   ^= enc[0];
                 data[i+1] ^= enc[1];
                 data[i+2] ^= enc[2];
                 data[i+3] ^= enc[3];
              }
              data = w.clamp(data, bl);

              // If encrypting, calculate hash
              if (encrypt) {
                tag = sjcl.mode.gcm._ghash(H, S0, data);
              }

              // Calculate last block from bit lengths, ugly because bitwise operations are 32-bit
              last = [
                Math.floor(abl/0x100000000), abl&0xffffffff,
                Math.floor(bl/0x100000000), bl&0xffffffff
              ];

              // Calculate the final tag block
              tag = sjcl.mode.gcm._ghash(H, tag, last);
              enc = prf.encrypt(J0);
              tag[0] ^= enc[0];
              tag[1] ^= enc[1];
              tag[2] ^= enc[2];
              tag[3] ^= enc[3];

              return { tag:w.bitSlice(tag, 0, tlen), data:data };
            }
          };
          /** @fileOverview HMAC implementation.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /** HMAC with the specified hash function.
           * @constructor
           * @param {bitArray} key the key for HMAC.
           * @param {Object} [hash=sjcl.hash.sha256] The hash function to use.
           */
          sjcl.misc.hmac = function (key, Hash) {
            this._hash = Hash = Hash || sjcl.hash.sha256;
            var exKey = [[],[]], i,
                bs = Hash.prototype.blockSize / 32;
            this._baseHash = [new Hash(), new Hash()];

            if (key.length > bs) {
              key = Hash.hash(key);
            }

            for (i=0; i<bs; i++) {
              exKey[0][i] = key[i]^0x36363636;
              exKey[1][i] = key[i]^0x5C5C5C5C;
            }

            this._baseHash[0].update(exKey[0]);
            this._baseHash[1].update(exKey[1]);
          };

          /** HMAC with the specified hash function.  Also called encrypt since it's a prf.
           * @param {bitArray|String} data The data to mac.
           */
          sjcl.misc.hmac.prototype.encrypt = sjcl.misc.hmac.prototype.mac = function (data) {
            var w = new (this._hash)(this._baseHash[0]).update(data).finalize();
            return new (this._hash)(this._baseHash[1]).update(w).finalize();
          };

          /** @fileOverview Password-based key-derivation function, version 2.0.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /** Password-Based Key-Derivation Function, version 2.0.
           *
           * Generate keys from passwords using PBKDF2-HMAC-SHA256.
           *
           * This is the method specified by RSA's PKCS #5 standard.
           *
           * @param {bitArray|String} password  The password.
           * @param {bitArray} salt The salt.  Should have lots of entropy.
           * @param {Number} [count=1000] The number of iterations.  Higher numbers make the function slower but more secure.
           * @param {Number} [length] The length of the derived key.  Defaults to the
                                      output size of the hash function.
           * @param {Object} [Prff=sjcl.misc.hmac] The pseudorandom function family.
           * @return {bitArray} the derived key.
           */
          sjcl.misc.pbkdf2 = function (password, salt, count, length, Prff) {
            count = count || 1000;

            if (length < 0 || count < 0) {
              throw sjcl.exception.invalid("invalid params to pbkdf2");
            }

            if (typeof password === "string") {
              password = sjcl.codec.utf8String.toBits(password);
            }

            Prff = Prff || sjcl.misc.hmac;

            var prf = new Prff(password),
                u, ui, i, j, k, out = [], b = sjcl.bitArray;

            for (k = 1; 32 * out.length < (length || 1); k++) {
              u = ui = prf.encrypt(b.concat(salt,[k]));

              for (i=1; i<count; i++) {
                ui = prf.encrypt(ui);
                for (j=0; j<ui.length; j++) {
                  u[j] ^= ui[j];
                }
              }

              out = out.concat(u);
            }

            if (length) { out = b.clamp(out, length); }

            return out;
          };

          /**
           * Same as sjcl.misc.pbkdf2, but splits the CPU intensive triple-nested for-loop for
           * the benefit of older browsers, such as IE7 and IE8.
           */
          sjcl.misc.pbkdf2_async = function (password, salt, count, length, Prff) {
            count = count || 1000;

            if (length < 0 || count < 0) {
              throw sjcl.exception.invalid("invalid params to pbkdf2");
            }

            if (typeof password === "string") {
              password = sjcl.codec.utf8String.toBits(password);
            }

            Prff = Prff || sjcl.misc.hmac;

            var prf = new Prff(password),
                u, ui, i, j, k, out = [], b = sjcl.bitArray;

            var totalIterationCounter = 0;
            k = 1;
            var outDeferred = $.Deferred();
            var safeIterator = function(normalIteration) {
              for (; 32 * out.length < (length || 1); k++) {
                if (normalIteration) {
                  u = ui = prf.encrypt(b.concat(salt,[k]));
                  i = 1;
                }

                for (; i<count; i++) {
                  if (normalIteration) {
                    ui = prf.encrypt(ui);
                    j = 0;
                  }

                  for (; j<ui.length; j++) {
                    if (totalIterationCounter++ % 10000 == 0) {
                      // Avoid hitting the browser's max synchronous operations limit.
                      window.setTimeout(safeIterator);
                      return;
                    }
                    normalIteration = true;
                    u[j] ^= ui[j];
                  }
                }

                out = out.concat(u);
                outDeferred.resolve(out);
              }
            };
            safeIterator(true);

            return outDeferred.then(function(out) {
              if (length) { out = b.clamp(out, length); }

              return out;
            });
          };


          /** @fileOverview Random number generator.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

          /** @constructor
           * @class Random number generator
           *
           * @description
           * <p>
           * This random number generator is a derivative of Ferguson and Schneier's
           * generator Fortuna.  It collects entropy from various events into several
           * pools, implemented by streaming SHA-256 instances.  It differs from
           * ordinary Fortuna in a few ways, though.
           * </p>
           *
           * <p>
           * Most importantly, it has an entropy estimator.  This is present because
           * there is a strong conflict here between making the generator available
           * as soon as possible, and making sure that it doesn't "run on empty".
           * In Fortuna, there is a saved state file, and the system is likely to have
           * time to warm up.
           * </p>
           *
           * <p>
           * Second, because users are unlikely to stay on the page for very long,
           * and to speed startup time, the number of pools increases logarithmically:
           * a new pool is created when the previous one is actually used for a reseed.
           * This gives the same asymptotic guarantees as Fortuna, but gives more
           * entropy to early reseeds.
           * </p>
           *
           * <p>
           * The entire mechanism here feels pretty klunky.  Furthermore, there are
           * several improvements that should be made, including support for
           * dedicated cryptographic functions that may be present in some browsers;
           * state files in local storage; cookies containing randomness; etc.  So
           * look for improvements in future versions.
           * </p>
           */
          sjcl.prng = function(defaultParanoia) {

            /* private */
            this._pools                   = [new sjcl.hash.sha256()];
            this._poolEntropy             = [0];
            this._reseedCount             = 0;
            this._robins                  = {};
            this._eventId                 = 0;

            this._collectorIds            = {};
            this._collectorIdNext         = 0;

            this._strength                = 0;
            this._poolStrength            = 0;
            this._nextReseed              = 0;
            this._key                     = [0,0,0,0,0,0,0,0];
            this._counter                 = [0,0,0,0];
            this._cipher                  = undefined;
            this._defaultParanoia         = defaultParanoia;

            /* event listener stuff */
            this._collectorsStarted       = false;
            this._callbacks               = {progress: {}, seeded: {}};
            this._callbackI               = 0;

            /* constants */
            this._NOT_READY               = 0;
            this._READY                   = 1;
            this._REQUIRES_RESEED         = 2;

            this._MAX_WORDS_PER_BURST     = 65536;
            this._PARANOIA_LEVELS         = [0,48,64,96,128,192,256,384,512,768,1024];
            this._MILLISECONDS_PER_RESEED = 30000;
            this._BITS_PER_RESEED         = 80;
          }

          sjcl.prng.prototype = {
            /** Generate several random words, and return them in an array
             * @param {Number} nwords The number of words to generate.
             */
            randomWords: function (nwords, paranoia) {
              var out = [], i, readiness = this.isReady(paranoia), g;

              if (readiness === this._NOT_READY) {
                throw new sjcl.exception.notReady("generator isn't seeded");
              } else if (readiness & this._REQUIRES_RESEED) {
                this._reseedFromPools(!(readiness & this._READY));
              }

              for (i=0; i<nwords; i+= 4) {
                if ((i+1) % this._MAX_WORDS_PER_BURST === 0) {
                  this._gate();
                }

                g = this._gen4words();
                out.push(g[0],g[1],g[2],g[3]);
              }
              this._gate();

              return out.slice(0,nwords);
            },

            setDefaultParanoia: function (paranoia) {
              this._defaultParanoia = paranoia;
            },

            /**
             * Add entropy to the pools.
             * @param data The entropic value.  Should be a 32-bit integer, array of 32-bit integers, or string
             * @param {Number} estimatedEntropy The estimated entropy of data, in bits
             * @param {String} source The source of the entropy, eg "mouse"
             */
            addEntropy: function (data, estimatedEntropy, source) {
              source = source || "user";

              var id,
                i, tmp,
                t = (new Date()).valueOf(),
                robin = this._robins[source],
                oldReady = this.isReady(), err = 0;

              id = this._collectorIds[source];
              if (id === undefined) { id = this._collectorIds[source] = this._collectorIdNext ++; }

              if (robin === undefined) { robin = this._robins[source] = 0; }
              this._robins[source] = ( this._robins[source] + 1 ) % this._pools.length;

              switch(typeof(data)) {

              case "number":
                if (estimatedEntropy === undefined) {
                  estimatedEntropy = 1;
                }
                this._pools[robin].update([id,this._eventId++,1,estimatedEntropy,t,1,data|0]);
                break;

              case "object":
                var objName = Object.prototype.toString.call(data);
                if (objName === "[object Uint32Array]") {
                  tmp = [];
                  for (i = 0; i < data.length; i++) {
                    tmp.push(data[i]);
                  }
                  data = tmp;
                } else {
                  if (objName !== "[object Array]") {
                    err = 1;
                  }
                  for (i=0; i<data.length && !err; i++) {
                    if (typeof(data[i]) != "number") {
                      err = 1;
                    }
                  }
                }
                if (!err) {
                  if (estimatedEntropy === undefined) {
                    /* horrible entropy estimator */
                    estimatedEntropy = 0;
                    for (i=0; i<data.length; i++) {
                      tmp= data[i];
                      while (tmp>0) {
                        estimatedEntropy++;
                        tmp = tmp >>> 1;
                      }
                    }
                  }
                  this._pools[robin].update([id,this._eventId++,2,estimatedEntropy,t,data.length].concat(data));
                }
                break;

              case "string":
                if (estimatedEntropy === undefined) {
                 /* English text has just over 1 bit per character of entropy.
                  * But this might be HTML or something, and have far less
                  * entropy than English...  Oh well, let's just say one bit.
                  */
                 estimatedEntropy = data.length;
                }
                this._pools[robin].update([id,this._eventId++,3,estimatedEntropy,t,data.length]);
                this._pools[robin].update(data);
                break;

              default:
                err=1;
              }
              if (err) {
                throw new sjcl.exception.bug("random: addEntropy only supports number, array of numbers or string");
              }

              /* record the new strength */
              this._poolEntropy[robin] += estimatedEntropy;
              this._poolStrength += estimatedEntropy;

              /* fire off events */
              if (oldReady === this._NOT_READY) {
                if (this.isReady() !== this._NOT_READY) {
                  this._fireEvent("seeded", Math.max(this._strength, this._poolStrength));
                }
                this._fireEvent("progress", this.getProgress());
              }
            },

            /** Is the generator ready? */
            isReady: function (paranoia) {
              var entropyRequired = this._PARANOIA_LEVELS[ (paranoia !== undefined) ? paranoia : this._defaultParanoia ];

              if (this._strength && this._strength >= entropyRequired) {
                return (this._poolEntropy[0] > this._BITS_PER_RESEED && (new Date()).valueOf() > this._nextReseed) ?
                  this._REQUIRES_RESEED | this._READY :
                  this._READY;
              } else {
                return (this._poolStrength >= entropyRequired) ?
                  this._REQUIRES_RESEED | this._NOT_READY :
                  this._NOT_READY;
              }
            },

            /** Get the generator's progress toward readiness, as a fraction */
            getProgress: function (paranoia) {
              var entropyRequired = this._PARANOIA_LEVELS[ paranoia ? paranoia : this._defaultParanoia ];

              if (this._strength >= entropyRequired) {
                return 1.0;
              } else {
                return (this._poolStrength > entropyRequired) ?
                  1.0 :
                  this._poolStrength / entropyRequired;
              }
            },

            /** start the built-in entropy collectors */
            startCollectors: function () {
              if (this._collectorsStarted) { return; }

              if (window.addEventListener) {
                window.addEventListener("load", this._loadTimeCollector, false);
                window.addEventListener("mousemove", this._mouseCollector, false);
              } else if (document.attachEvent) {
                document.attachEvent("onload", this._loadTimeCollector);
                document.attachEvent("onmousemove", this._mouseCollector);
              }
              else {
                throw new sjcl.exception.bug("can't attach event");
              }

              this._collectorsStarted = true;
            },

            /** stop the built-in entropy collectors */
            stopCollectors: function () {
              if (!this._collectorsStarted) { return; }

              if (window.removeEventListener) {
                window.removeEventListener("load", this._loadTimeCollector, false);
                window.removeEventListener("mousemove", this._mouseCollector, false);
              } else if (window.detachEvent) {
                window.detachEvent("onload", this._loadTimeCollector);
                window.detachEvent("onmousemove", this._mouseCollector);
              }
              this._collectorsStarted = false;
            },

            /* use a cookie to store entropy.
            useCookie: function (all_cookies) {
                throw new sjcl.exception.bug("random: useCookie is unimplemented");
            },*/

            /** add an event listener for progress or seeded-ness. */
            addEventListener: function (name, callback) {
              this._callbacks[name][this._callbackI++] = callback;
            },

            /** remove an event listener for progress or seeded-ness */
            removeEventListener: function (name, cb) {
              var i, j, cbs=this._callbacks[name], jsTemp=[];

              /* I'm not sure if this is necessary; in C++, iterating over a
               * collection and modifying it at the same time is a no-no.
               */

              for (j in cbs) {
            if (cbs.hasOwnProperty(j) && cbs[j] === cb) {
                  jsTemp.push(j);
                }
              }

              for (i=0; i<jsTemp.length; i++) {
                j = jsTemp[i];
                delete cbs[j];
              }
            },

            /** Generate 4 random words, no reseed, no gate.
             * @private
             */
            _gen4words: function () {
              for (var i=0; i<4; i++) {
                this._counter[i] = this._counter[i]+1 | 0;
                if (this._counter[i]) { break; }
              }
              return this._cipher.encrypt(this._counter);
            },

            /* Rekey the AES instance with itself after a request, or every _MAX_WORDS_PER_BURST words.
             * @private
             */
            _gate: function () {
              this._key = this._gen4words().concat(this._gen4words());
              this._cipher = new sjcl.cipher.aes(this._key);
            },

            /** Reseed the generator with the given words
             * @private
             */
            _reseed: function (seedWords) {
              this._key = sjcl.hash.sha256.hash(this._key.concat(seedWords));
              this._cipher = new sjcl.cipher.aes(this._key);
              for (var i=0; i<4; i++) {
                this._counter[i] = this._counter[i]+1 | 0;
                if (this._counter[i]) { break; }
              }
            },

            /** reseed the data from the entropy pools
             * @param full If set, use all the entropy pools in the reseed.
             */
            _reseedFromPools: function (full) {
              var reseedData = [], strength = 0, i;

              this._nextReseed = reseedData[0] =
                (new Date()).valueOf() + this._MILLISECONDS_PER_RESEED;

              for (i=0; i<16; i++) {
                /* On some browsers, this is cryptographically random.  So we might
                 * as well toss it in the pot and stir...
                 */
                reseedData.push(Math.random()*0x100000000|0);
              }

              for (i=0; i<this._pools.length; i++) {
               reseedData = reseedData.concat(this._pools[i].finalize());
               strength += this._poolEntropy[i];
               this._poolEntropy[i] = 0;

               if (!full && (this._reseedCount & (1<<i))) { break; }
              }

              /* if we used the last pool, push a new one onto the stack */
              if (this._reseedCount >= 1 << this._pools.length) {
               this._pools.push(new sjcl.hash.sha256());
               this._poolEntropy.push(0);
              }

              /* how strong was this reseed? */
              this._poolStrength -= strength;
              if (strength > this._strength) {
                this._strength = strength;
              }

              this._reseedCount ++;
              this._reseed(reseedData);
            },

            _mouseCollector: function (ev) {
              var x = ev.x || ev.clientX || ev.offsetX || 0, y = ev.y || ev.clientY || ev.offsetY || 0;
              sjcl.random.addEntropy([x,y], 2, "mouse");
            },

            _loadTimeCollector: function (ev) {
              sjcl.random.addEntropy((new Date()).valueOf(), 2, "loadtime");
            },

            _fireEvent: function (name, arg) {
              var j, cbs=sjcl.random._callbacks[name], cbsTemp=[];
              /* TODO: there is a race condition between removing collectors and firing them */

              /* I'm not sure if this is necessary; in C++, iterating over a
               * collection and modifying it at the same time is a no-no.
               */

              for (j in cbs) {
               if (cbs.hasOwnProperty(j)) {
                  cbsTemp.push(cbs[j]);
               }
              }

              for (j=0; j<cbsTemp.length; j++) {
               cbsTemp[j](arg);
              }
            }
          };

          sjcl.random = new sjcl.prng(6);

          (function(){
            try {
              // get cryptographically strong entropy in Webkit
              var ab = new Uint32Array(32);
              crypto.getRandomValues(ab);
              sjcl.random.addEntropy(ab, 1024, "crypto.getRandomValues");
            } catch (e) {
              // no getRandomValues :-(
            }
          })();
          /** @fileOverview Convenince functions centered around JSON encapsulation.
           *
           * @author Emily Stark
           * @author Mike Hamburg
           * @author Dan Boneh
           */

           /** @namespace JSON encapsulation */
           sjcl.json = {
            /** Default values for encryption */
            defaults: { v:1, iter:1000, ks:128, ts:64, mode:"ccm", adata:"", cipher:"aes" },

            /** Simple encryption function.
             * @param {String|bitArray} password The password or key.
             * @param {String} plaintext The data to encrypt.
             * @param {Object} [params] The parameters including tag, iv and salt.
             * @param {Object} [rp] A returned version with filled-in parameters.
             * @return {String} The ciphertext.
             * @throws {sjcl.exception.invalid} if a parameter is invalid.
             */
            encrypt: function (password, plaintext, params, rp) {
              params = params || {};
              rp = rp || {};

              var j = sjcl.json, p = j._add({ iv: sjcl.random.randomWords(4,0) },
                                            j.defaults), tmp, prp, adata;
              j._add(p, params);
              adata = p.adata;
              if (typeof p.salt === "string") {
                p.salt = sjcl.codec.base64.toBits(p.salt);
              }
              if (typeof p.iv === "string") {
                p.iv = sjcl.codec.base64.toBits(p.iv);
              }

              if (!sjcl.mode[p.mode] ||
                  !sjcl.cipher[p.cipher] ||
                  (typeof password === "string" && p.iter <= 100) ||
                  (p.ts !== 64 && p.ts !== 96 && p.ts !== 128) ||
                  (p.ks !== 128 && p.ks !== 192 && p.ks !== 256) ||
                  (p.iv.length < 2 || p.iv.length > 4)) {
                throw new sjcl.exception.invalid("json encrypt: invalid parameters");
              }

              if (typeof password === "string") {
                tmp = sjcl.misc.cachedPbkdf2(password, p);
                password = tmp.key.slice(0,p.ks/32);
                p.salt = tmp.salt;
              } else if (sjcl.ecc && password instanceof sjcl.ecc.elGamal.publicKey) {
                tmp = password.kem();
                p.kemtag = tmp.tag;
                password = tmp.key.slice(0,p.ks/32);
              }
              if (typeof plaintext === "string") {
                plaintext = sjcl.codec.utf8String.toBits(plaintext);
              }
              if (typeof adata === "string") {
                adata = sjcl.codec.utf8String.toBits(adata);
              }
              prp = new sjcl.cipher[p.cipher](password);

              /* return the json data */
              j._add(rp, p);
              rp.key = password;

              /* do the encryption */
              p.ct = sjcl.mode[p.mode].encrypt(prp, plaintext, p.iv, adata, p.ts);

              //return j.encode(j._subtract(p, j.defaults));
              return j.encode(p);
            },

            /** Simple decryption function.
             * @param {String|bitArray} password The password or key.
             * @param {String} ciphertext The ciphertext to decrypt.
             * @param {Object} [params] Additional non-default parameters.
             * @param {Object} [rp] A returned object with filled parameters.
             * @return {String} The plaintext.
             * @throws {sjcl.exception.invalid} if a parameter is invalid.
             * @throws {sjcl.exception.corrupt} if the ciphertext is corrupt.
             */
            decrypt: function (password, ciphertext, params, rp) {
              params = params || {};
              rp = rp || {};

              var j = sjcl.json, p = j._add(j._add(j._add({},j.defaults),j.decode(ciphertext)), params, true), ct, tmp, prp, adata=p.adata;
              if (typeof p.salt === "string") {
                p.salt = sjcl.codec.base64.toBits(p.salt);
              }
              if (typeof p.iv === "string") {
                p.iv = sjcl.codec.base64.toBits(p.iv);
              }

              if (!sjcl.mode[p.mode] ||
                  !sjcl.cipher[p.cipher] ||
                  (typeof password === "string" && p.iter <= 100) ||
                  (p.ts !== 64 && p.ts !== 96 && p.ts !== 128) ||
                  (p.ks !== 128 && p.ks !== 192 && p.ks !== 256) ||
                  (!p.iv) ||
                  (p.iv.length < 2 || p.iv.length > 4)) {
                throw new sjcl.exception.invalid("json decrypt: invalid parameters");
              }

              if (typeof password === "string") {
                tmp = sjcl.misc.cachedPbkdf2(password, p);
                password = tmp.key.slice(0,p.ks/32);
                p.salt  = tmp.salt;
              } else if (sjcl.ecc && password instanceof sjcl.ecc.elGamal.secretKey) {
                password = password.unkem(sjcl.codec.base64.toBits(p.kemtag)).slice(0,p.ks/32);
              }
              if (typeof adata === "string") {
                adata = sjcl.codec.utf8String.toBits(adata);
              }
              prp = new sjcl.cipher[p.cipher](password);

              /* do the decryption */
              ct = sjcl.mode[p.mode].decrypt(prp, p.ct, p.iv, adata, p.ts);

              /* return the json data */
              j._add(rp, p);
              rp.key = password;

              return sjcl.codec.utf8String.fromBits(ct);
            },

            /** Encode a flat structure into a JSON string.
             * @param {Object} obj The structure to encode.
             * @return {String} A JSON string.
             * @throws {sjcl.exception.invalid} if obj has a non-alphanumeric property.
             * @throws {sjcl.exception.bug} if a parameter has an unsupported type.
             */
            encode: function (obj) {
              var i, out='{', comma='';
              for (i in obj) {
                if (obj.hasOwnProperty(i)) {
                  if (!i.match(/^[a-z0-9]+$/i)) {
                    throw new sjcl.exception.invalid("json encode: invalid property name");
                  }
                  out += comma + '"' + i + '":';
                  comma = ',';

                  switch (typeof obj[i]) {
                  case 'number':
                  case 'boolean':
                    out += obj[i];
                    break;

                  case 'string':
                    out += '"' + escape(obj[i]) + '"';
                    break;

                  case 'object':
                    out += '"' + sjcl.codec.base64.fromBits(obj[i],0) + '"';
                    break;

                  default:
                    throw new sjcl.exception.bug("json encode: unsupported type");
                  }
                }
              }
              return out+'}';
            },

            /** Decode a simple (flat) JSON string into a structure.  The ciphertext,
             * adata, salt and iv will be base64-decoded.
             * @param {String} str The string.
             * @return {Object} The decoded structure.
             * @throws {sjcl.exception.invalid} if str isn't (simple) JSON.
             */
            decode: function (str) {
              str = str.replace(/\s/g,'');
              if (!str.match(/^\{.*\}$/)) {
                throw new sjcl.exception.invalid("json decode: this isn't json!");
              }
              var a = str.replace(/^\{|\}$/g, '').split(/,/), out={}, i, m;
              for (i=0; i<a.length; i++) {
                if (!(m=a[i].match(/^(?:(["']?)([a-z][a-z0-9]*)\1):(?:(\d+)|"([a-z0-9+\/%*_.@=\-]*)")$/i))) {
                  throw new sjcl.exception.invalid("json decode: this isn't json!");
                }
                if (m[3]) {
                  out[m[2]] = parseInt(m[3],10);
                } else {
                  out[m[2]] = m[2].match(/^(ct|salt|iv)$/) ? sjcl.codec.base64.toBits(m[4]) : unescape(m[4]);
                }
              }
              return out;
            },

            /** Insert all elements of src into target, modifying and returning target.
             * @param {Object} target The object to be modified.
             * @param {Object} src The object to pull data from.
             * @param {boolean} [requireSame=false] If true, throw an exception if any field of target differs from corresponding field of src.
             * @return {Object} target.
             * @private
             */
            _add: function (target, src, requireSame) {
              if (target === undefined) { target = {}; }
              if (src === undefined) { return target; }
              var i;
              for (i in src) {
                if (src.hasOwnProperty(i)) {
                  if (requireSame && target[i] !== undefined && target[i] !== src[i]) {
                    throw new sjcl.exception.invalid("required parameter overridden");
                  }
                  target[i] = src[i];
                }
              }
              return target;
            },

            /** Remove all elements of minus from plus.  Does not modify plus.
             * @private
             */
            _subtract: function (plus, minus) {
              var out = {}, i;

              for (i in plus) {
                if (plus.hasOwnProperty(i) && plus[i] !== minus[i]) {
                  out[i] = plus[i];
                }
              }

              return out;
            },

            /** Return only the specified elements of src.
             * @private
             */
            _filter: function (src, filter) {
              var out = {}, i;
              for (i=0; i<filter.length; i++) {
                if (src[filter[i]] !== undefined) {
                  out[filter[i]] = src[filter[i]];
                }
              }
              return out;
            }
          };

          /** Simple encryption function; convenient shorthand for sjcl.json.encrypt.
           * @param {String|bitArray} password The password or key.
           * @param {String} plaintext The data to encrypt.
           * @param {Object} [params] The parameters including tag, iv and salt.
           * @param {Object} [rp] A returned version with filled-in parameters.
           * @return {String} The ciphertext.
           */
          sjcl.encrypt = sjcl.json.encrypt;

          /** Simple decryption function; convenient shorthand for sjcl.json.decrypt.
           * @param {String|bitArray} password The password or key.
           * @param {String} ciphertext The ciphertext to decrypt.
           * @param {Object} [params] Additional non-default parameters.
           * @param {Object} [rp] A returned object with filled parameters.
           * @return {String} The plaintext.
           */
          sjcl.decrypt = sjcl.json.decrypt;

          /** The cache for cachedPbkdf2.
           * @private
           */
          sjcl.misc._pbkdf2Cache = {};

          /** Cached PBKDF2 key derivation.
           * @param {String} password The password.
           * @param {Object} [params] The derivation params (iteration count and optional salt).
           * @return {Object} The derived data in key, the salt in salt.
           */
          sjcl.misc.cachedPbkdf2 = function (password, obj) {
            var cache = sjcl.misc._pbkdf2Cache, c, cp, str, salt, iter;

            obj = obj || {};
            iter = obj.iter || 1000;

            /* open the cache for this password and iteration count */
            cp = cache[password] = cache[password] || {};
            c = cp[iter] = cp[iter] || { firstSalt: (obj.salt && obj.salt.length) ?
                               obj.salt.slice(0) : sjcl.random.randomWords(2,0) };

            salt = (obj.salt === undefined) ? c.firstSalt : obj.salt;

            c[salt] = c[salt] || sjcl.misc.pbkdf2(password, salt, obj.iter);
            return { key: c[salt].slice(0), salt:salt.slice(0) };
          };

          return sjcl;
        })({}); // sjcl
        // /\ jQuery should be there. It's used for Deferred calls on async decrypt.

        /**
         * Taken from js/en/crypto.js of common-editor (branch: develop) as of commit 69296310.
         * Changes:
         *   - Wrap in define block. Return decrypt() and encrypt() in a JS object.
         *   - Set "DEBUG" to false.
         *   - Add decrypt_async for an IE7/8 fix (WEB-21996).
         */
        var aesCrypto = (function(sjcl) {
            // This is required in order to make CBC work
            sjcl.beware["CBC mode is dangerous because it doesn't protect message integrity."]();

            var DEBUG = false;
            var BYTE_LEN = 8;
            var WORD_LEN = 32;

            // Evernote Crypto Settings
            var EN_ITERATIONS = 50000;
            var EN_KEYSIZE = 128;
            // var EN_CIPHER        = "aes"
            // var EN_MODE          = "cbc"
            var EN_HMACSIZE = 32 * BYTE_LEN;
            var EN_IDENT = 'ENC0';

            /**
             * PBKDF2
             * @param  {string} password
             * @param  {string} salt
             * @return {string}
             */
            function calcKey(password, salt) {
                if (!password || !salt) {
                    DEBUG && en.console.error('Missing required argument.');
                    throw 'Missing required argument';
                }
                return sjcl.misc.pbkdf2(password, salt, EN_ITERATIONS, EN_KEYSIZE);
            }

            /**
             * Same as calcKey, but calls SJCL methods to break up CPU intensive operations into
             * separate browser event loop calls for the benefit of older browsers, such as IE7
             * and IE8.
             */
            function calcKey_async(password, salt) {
                if (!password || !salt) {
                    DEBUG && en.console.error('Missing required argument.');
                    throw 'Missing required argument';
                }
                return sjcl.misc.pbkdf2_async(password, salt, EN_ITERATIONS, EN_KEYSIZE);
            }

            /**
             * Decrypt
             * @param  {string} password
             * @param  {string} data
             * @return {string}
             */
            function decrypt(password, data) {
                if (typeof data === 'string') {
                    data = sjcl.codec.base64.toBits(data);
                }

                var cursor = BYTE_LEN * EN_IDENT.length;

                // var info = sjcl.bitArray.bitSlice(data, 0, cursor);
                if (EN_IDENT !== sjcl.codec.utf8String.fromBits([data[0]])) {
                    DEBUG && en.console.error('No Evernote crypto data.');
                    throw 'This is not Evernote crypto data.';
                }

                var salt = sjcl.bitArray.bitSlice(data, cursor, cursor + EN_KEYSIZE);
                cursor += EN_KEYSIZE;

                var saltHMAC = sjcl.bitArray.bitSlice(data, cursor, cursor + EN_KEYSIZE);
                cursor += EN_KEYSIZE;

                var iv = sjcl.bitArray.bitSlice(data, cursor, cursor + EN_KEYSIZE);
                cursor += EN_KEYSIZE;

                var dataLen = sjcl.bitArray.bitLength(data);
                var ct = sjcl.bitArray.bitSlice(data, cursor, dataLen - EN_HMACSIZE);
                cursor += dataLen - EN_HMACSIZE - cursor;

                var hmacExpected = sjcl.bitArray.bitSlice(data, cursor, cursor + EN_HMACSIZE);

                // Check validity
                var keyHMAC = calcKey(password, saltHMAC);
                var hmac = new sjcl.misc.hmac(keyHMAC).encrypt(sjcl.bitArray.bitSlice(data, 0, dataLen - EN_HMACSIZE));
                if (!sjcl.bitArray.equal(hmac, hmacExpected)) {
                    DEBUG && en.console.error('Invalid checksum.', hmac, hmacExpected);
                    throw 'Invalid checksum.';
                }

                // Decrypt
                var key = calcKey(password, salt);
                var prp = new sjcl.cipher.aes(key);
                var result = sjcl.mode.cbc.decrypt(
                    prp,
                    ct,
                    iv
                    );

                return sjcl.codec.utf8String.fromBits(result);
            }

            /**
             * Same as decrypt, but calls SJCL methods to break up CPU intensive operations into
             * separate browser event loop calls for the benefit of older browsers, such as IE7
             * and IE8.
             */
            function decrypt_async(password, data) {
                try {
                  if (typeof data === 'string') {
                      data = sjcl.codec.base64.toBits(data);
                  }

                  var cursor = BYTE_LEN * EN_IDENT.length;

                  // var info = sjcl.bitArray.bitSlice(data, 0, cursor);
                  if (EN_IDENT !== sjcl.codec.utf8String.fromBits([data[0]])) {
                      DEBUG && en.console.error('No Evernote crypto data.');
                      throw 'This is not Evernote crypto data.';

                  }

                  var salt = sjcl.bitArray.bitSlice(data, cursor, cursor + EN_KEYSIZE);
                  cursor += EN_KEYSIZE;

                  var saltHMAC = sjcl.bitArray.bitSlice(data, cursor, cursor + EN_KEYSIZE);
                  cursor += EN_KEYSIZE;

                  var iv = sjcl.bitArray.bitSlice(data, cursor, cursor + EN_KEYSIZE);
                  cursor += EN_KEYSIZE;

                  var dataLen = sjcl.bitArray.bitLength(data);
                  var ct = sjcl.bitArray.bitSlice(data, cursor, dataLen - EN_HMACSIZE);
                  cursor += dataLen - EN_HMACSIZE - cursor;

                  var hmacExpected = sjcl.bitArray.bitSlice(data, cursor, cursor + EN_HMACSIZE);

                  // Check validity
                  return calcKey_async(password, saltHMAC).then(function(keyHMAC) {
                    try{
                      var hmac = new sjcl.misc.hmac(keyHMAC).encrypt(sjcl.bitArray.bitSlice(data,
                          0, dataLen - EN_HMACSIZE));
                      if (!sjcl.bitArray.equal(hmac, hmacExpected)) {
                          DEBUG && en.console.error('Invalid checksum.', hmac, hmacExpected);
                          throw 'Invalid checksum.';
                      }
                      return calcKey_async(password, salt);
                    } catch (e) {
                      return $.Deferred().reject(e);
                    }
                  }).then(function(key) {
                    try {
                      // Decrypt
                      var prp = new sjcl.cipher.aes(key);
                      var result = sjcl.mode.cbc.decrypt(
                          prp,
                          ct,
                          iv
                          );
                      return sjcl.codec.utf8String.fromBits(result);
                    } catch (e) {
                      return $.Deferred().reject(e);
                    }
                  });
                } catch (e) {
                  return $.Deferred().reject(e);
                }
            }

            /**
             * Encrypt
             * @param  {string} password
             * @param  {string} plaintext
             * @return {string}
             */
            function encrypt(password, plaintext) {
                if (typeof plaintext === 'string') {
                    plaintext = sjcl.codec.utf8String.toBits(plaintext);
                }

                // Generate key
                var salt = sjcl.random.randomWords(EN_KEYSIZE / WORD_LEN, 0);
                var saltHMAC = sjcl.random.randomWords(EN_KEYSIZE / WORD_LEN, 0);

                var key = calcKey(password, salt);
                var keyHMAC = calcKey(password, saltHMAC);

                // Encrypt
                var iv = sjcl.random.randomWords(EN_KEYSIZE / WORD_LEN, 0);
                var prp = new sjcl.cipher.aes(key);
                var ct = sjcl.mode.cbc.encrypt(
                    prp,
                    plaintext,
                    iv
                    );

                var result = [].concat(
                    sjcl.codec.utf8String.toBits(EN_IDENT),
                    salt,
                    saltHMAC,
                    iv,
                    ct);

                var hmac = new sjcl.misc.hmac(keyHMAC).encrypt(result);
                result = result.concat(hmac);

                var data = sjcl.codec.base64.fromBits(result);
                return data;
            }

            return {
              decrypt : decrypt,
              decrypt_async : decrypt_async,
              encrypt : encrypt
            };
        })(sjcl); // aesCrypto

        return aesCrypto;
    })(); // evernoteAesCrypto

    var evernoteDecrypt = (function() {
        // base64.js
        /**
         * Adapted from: http://www.webtoolkit.info/javascript-base64.html
         * License: http://www.webtoolkit.info/licence.html
         * Which reads (2009-08-04):
         * As long as you leave the copyright notice of the original script, or link back to this website, you can use any of the content published on this website free of charge for any use: commercial or noncommercial.
         */

        var Base64 = {

          keyStr : "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",

          encode : function (input) {
             var output = "";
             var chr1, chr2, chr3 = "";
             var enc1, enc2, enc3, enc4 = "";
             var i = 0;

             do {
                chr1 = input.charCodeAt(i++);
                chr2 = input.charCodeAt(i++);
                chr3 = input.charCodeAt(i++);

                enc1 = chr1 >> 2;
                enc2 = ((chr1 & 3) << 4) | (chr2 >> 4);
                enc3 = ((chr2 & 15) << 2) | (chr3 >> 6);
                enc4 = chr3 & 63;

                if (isNaN(chr2)) {
                   enc3 = enc4 = 64;
                } else if (isNaN(chr3)) {
                   enc4 = 64;
                }

                output = output +
                   this.keyStr.charAt(enc1) +
                   this.keyStr.charAt(enc2) +
                   this.keyStr.charAt(enc3) +
                   this.keyStr.charAt(enc4);
                chr1 = chr2 = chr3 = "";
                enc1 = enc2 = enc3 = enc4 = "";
             } while (i < input.length);

             return output;
          },

          decode: function (input) {
             var output = "";
             var chr1, chr2, chr3 = "";
             var enc1, enc2, enc3, enc4 = "";
             var i = 0;

             // remove all characters that are not A-Z, a-z, 0-9, +, /, or =
             var base64test = /[^A-Za-z0-9\+\/\=]/g;
             if (base64test.exec(input)) {
                alert("There were invalid base64 characters in the input text.\n" +
                      "Valid base64 characters are A-Z, a-z, 0-9, '+', '/',and '='\n" +
                      "Expect errors in decoding.");
             }
             input = input.replace(/[^A-Za-z0-9\+\/\=]/g, "");

             do {
                enc1 = this.keyStr.indexOf(input.charAt(i++));
                enc2 = this.keyStr.indexOf(input.charAt(i++));
                enc3 = this.keyStr.indexOf(input.charAt(i++));
                enc4 = this.keyStr.indexOf(input.charAt(i++));

                chr1 = (enc1 << 2) | (enc2 >> 4);
                chr2 = ((enc2 & 15) << 4) | (enc3 >> 2);
                chr3 = ((enc3 & 3) << 6) | enc4;

                output = output + String.fromCharCode(chr1);

                if (enc3 != 64) {
                   output = output + String.fromCharCode(chr2);
                }
                if (enc4 != 64) {
                   output = output + String.fromCharCode(chr3);
                }

                chr1 = chr2 = chr3 = "";
                enc1 = enc2 = enc3 = enc4 = "";

             } while (i < input.length);

             return output;
          }

        } // end of Base64 namespace

        // crc32.js
        /**
         * From: http://www.webtoolkit.info/javascript-crc32.html
         * License: http://www.webtoolkit.info/licence.html
         * Which reads (2009-08-04):
         * As long as you leave the copyright notice of the original script, or link back to this website, you can use any of the content published on this website free of charge for any use: commercial or noncommercial.
         */
        /**
        *
        *  Javascript crc32
        *  http://www.webtoolkit.info/
        *
        **/

        function crc32 (str, crc) { // String should be ASCII (or UTF8-encoded)
            var table = "00000000 77073096 EE0E612C 990951BA 076DC419 " +
                        "706AF48F E963A535 9E6495A3 0EDB8832 79DCB8A4 " +
                        "E0D5E91E 97D2D988 09B64C2B 7EB17CBD E7B82D07 " +
                        "90BF1D91 1DB71064 6AB020F2 F3B97148 84BE41DE " +
                        "1ADAD47D 6DDDE4EB F4D4B551 83D385C7 136C9856 " +
                        "646BA8C0 FD62F97A 8A65C9EC 14015C4F 63066CD9 " +
                        "FA0F3D63 8D080DF5 3B6E20C8 4C69105E D56041E4 " +
                        "A2677172 3C03E4D1 4B04D447 D20D85FD A50AB56B " +
                        "35B5A8FA 42B2986C DBBBC9D6 ACBCF940 32D86CE3 " +
                        "45DF5C75 DCD60DCF ABD13D59 26D930AC 51DE003A " +
                        "C8D75180 BFD06116 21B4F4B5 56B3C423 CFBA9599 " +
                        "B8BDA50F 2802B89E 5F058808 C60CD9B2 B10BE924 " +
                        "2F6F7C87 58684C11 C1611DAB B6662D3D 76DC4190 " +
                        "01DB7106 98D220BC EFD5102A 71B18589 06B6B51F " +
                        "9FBFE4A5 E8B8D433 7807C9A2 0F00F934 9609A88E " +
                        "E10E9818 7F6A0DBB 086D3D2D 91646C97 E6635C01 " +
                        "6B6B51F4 1C6C6162 856530D8 F262004E 6C0695ED " +
                        "1B01A57B 8208F4C1 F50FC457 65B0D9C6 12B7E950 " +
                        "8BBEB8EA FCB9887C 62DD1DDF 15DA2D49 8CD37CF3 " +
                        "FBD44C65 4DB26158 3AB551CE A3BC0074 D4BB30E2 " +
                        "4ADFA541 3DD895D7 A4D1C46D D3D6F4FB 4369E96A " +
                        "346ED9FC AD678846 DA60B8D0 44042D73 33031DE5 " +
                        "AA0A4C5F DD0D7CC9 5005713C 270241AA BE0B1010 " +
                        "C90C2086 5768B525 206F85B3 B966D409 CE61E49F " +
                        "5EDEF90E 29D9C998 B0D09822 C7D7A8B4 59B33D17 " +
                        "2EB40D81 B7BD5C3B C0BA6CAD EDB88320 9ABFB3B6 " +
                        "03B6E20C 74B1D29A EAD54739 9DD277AF 04DB2615 " +
                        "73DC1683 E3630B12 94643B84 0D6D6A3E 7A6A5AA8 " +
                        "E40ECF0B 9309FF9D 0A00AE27 7D079EB1 F00F9344 " +
                        "8708A3D2 1E01F268 6906C2FE F762575D 806567CB " +
                        "196C3671 6E6B06E7 FED41B76 89D32BE0 10DA7A5A " +
                        "67DD4ACC F9B9DF6F 8EBEEFF9 17B7BE43 60B08ED5 " +
                        "D6D6A3E8 A1D1937E 38D8C2C4 4FDFF252 D1BB67F1 " +
                        "A6BC5767 3FB506DD 48B2364B D80D2BDA AF0A1B4C " +
                        "36034AF6 41047A60 DF60EFC3 A867DF55 316E8EEF " +
                        "4669BE79 CB61B38C BC66831A 256FD2A0 5268E236 " +
                        "CC0C7795 BB0B4703 220216B9 5505262F C5BA3BBE " +
                        "B2BD0B28 2BB45A92 5CB36A04 C2D7FFA7 B5D0CF31 " +
                        "2CD99E8B 5BDEAE1D 9B64C2B0 EC63F226 756AA39C " +
                        "026D930A 9C0906A9 EB0E363F 72076785 05005713 " +
                        "95BF4A82 E2B87A14 7BB12BAE 0CB61B38 92D28E9B " +
                        "E5D5BE0D 7CDCEFB7 0BDBDF21 86D3D2D4 F1D4E242 " +
                        "68DDB3F8 1FDA836E 81BE16CD F6B9265B 6FB077E1 " +
                        "18B74777 88085AE6 FF0F6A70 66063BCA 11010B5C " +
                        "8F659EFF F862AE69 616BFFD3 166CCF45 A00AE278 " +
                        "D70DD2EE 4E048354 3903B3C2 A7672661 D06016F7 " +
                        "4969474D 3E6E77DB AED16A4A D9D65ADC 40DF0B66 " +
                        "37D83BF0 A9BCAE53 DEBB9EC5 47B2CF7F 30B5FFE9 " +
                        "BDBDF21C CABAC28A 53B39330 24B4A3A6 BAD03605 " +
                        "CDD70693 54DE5729 23D967BF B3667A2E C4614AB8 " +
                        "5D681B02 2A6F2B94 B40BBE37 C30C8EA1 5A05DF1B " +
                        "2D02EF8D";

            if (typeof(crc) == "undefined") { crc = 0; }
            var x = 0;
            var y = 0;

            crc = crc ^ (-1);
            for( var i = 0, iTop = str.length; i < iTop; i++ ) {
                y = ( crc ^ str.charCodeAt( i ) ) & 0xFF;
                x = "0x" + table.substr( y * 9, 8 );
                crc = ( crc >>> 8 ) ^ x;
            }

            return crc ^ (-1);
        };

        // md5.cs
        // from: http://www.onicos.com/staff/iz/amuse/javascript/expert/md5.txt
        /* md5.js - MD5 Message-Digest
         * Copyright (C) 1999,2002 Masanao Izumo <iz@onicos.co.jp>
         * Version: 2.0.0
         * LastModified: May 13 2002
         *
         * This program is free software.  You can redistribute it and/or modify
         * it without any warranty.  This library calculates the MD5 based on RFC1321.
         * See RFC1321 for more information and algorism.
         */

        /* Interface:
         * md5_128bits = MD5_hash(data);
         * md5_hexstr = MD5_hexhash(data);
         */

        /* ChangeLog
         * 2002/05/13: Version 2.0.0 released
         * NOTICE: API is changed.
         * 2002/04/15: Bug fix about MD5 length.
         */


        //    md5_T[i] = parseInt(Math.abs(Math.sin(i)) * 4294967296.0);
        var MD5_T = new Array(0x00000000, 0xd76aa478, 0xe8c7b756, 0x242070db,
                      0xc1bdceee, 0xf57c0faf, 0x4787c62a, 0xa8304613,
                      0xfd469501, 0x698098d8, 0x8b44f7af, 0xffff5bb1,
                      0x895cd7be, 0x6b901122, 0xfd987193, 0xa679438e,
                      0x49b40821, 0xf61e2562, 0xc040b340, 0x265e5a51,
                      0xe9b6c7aa, 0xd62f105d, 0x02441453, 0xd8a1e681,
                      0xe7d3fbc8, 0x21e1cde6, 0xc33707d6, 0xf4d50d87,
                      0x455a14ed, 0xa9e3e905, 0xfcefa3f8, 0x676f02d9,
                      0x8d2a4c8a, 0xfffa3942, 0x8771f681, 0x6d9d6122,
                      0xfde5380c, 0xa4beea44, 0x4bdecfa9, 0xf6bb4b60,
                      0xbebfbc70, 0x289b7ec6, 0xeaa127fa, 0xd4ef3085,
                      0x04881d05, 0xd9d4d039, 0xe6db99e5, 0x1fa27cf8,
                      0xc4ac5665, 0xf4292244, 0x432aff97, 0xab9423a7,
                      0xfc93a039, 0x655b59c3, 0x8f0ccc92, 0xffeff47d,
                      0x85845dd1, 0x6fa87e4f, 0xfe2ce6e0, 0xa3014314,
                      0x4e0811a1, 0xf7537e82, 0xbd3af235, 0x2ad7d2bb,
                      0xeb86d391);

        var MD5_round1 = new Array(new Array( 0, 7, 1), new Array( 1,12, 2),
                       new Array( 2,17, 3), new Array( 3,22, 4),
                       new Array( 4, 7, 5), new Array( 5,12, 6),
                       new Array( 6,17, 7), new Array( 7,22, 8),
                       new Array( 8, 7, 9), new Array( 9,12,10),
                       new Array(10,17,11), new Array(11,22,12),
                       new Array(12, 7,13), new Array(13,12,14),
                       new Array(14,17,15), new Array(15,22,16));

        var MD5_round2 = new Array(new Array( 1, 5,17), new Array( 6, 9,18),
                       new Array(11,14,19), new Array( 0,20,20),
                       new Array( 5, 5,21), new Array(10, 9,22),
                       new Array(15,14,23), new Array( 4,20,24),
                       new Array( 9, 5,25), new Array(14, 9,26),
                       new Array( 3,14,27), new Array( 8,20,28),
                       new Array(13, 5,29), new Array( 2, 9,30),
                       new Array( 7,14,31), new Array(12,20,32));

        var MD5_round3 = new Array(new Array( 5, 4,33), new Array( 8,11,34),
                       new Array(11,16,35), new Array(14,23,36),
                       new Array( 1, 4,37), new Array( 4,11,38),
                       new Array( 7,16,39), new Array(10,23,40),
                       new Array(13, 4,41), new Array( 0,11,42),
                       new Array( 3,16,43), new Array( 6,23,44),
                       new Array( 9, 4,45), new Array(12,11,46),
                       new Array(15,16,47), new Array( 2,23,48));

        var MD5_round4 = new Array(new Array( 0, 6,49), new Array( 7,10,50),
                       new Array(14,15,51), new Array( 5,21,52),
                       new Array(12, 6,53), new Array( 3,10,54),
                       new Array(10,15,55), new Array( 1,21,56),
                       new Array( 8, 6,57), new Array(15,10,58),
                       new Array( 6,15,59), new Array(13,21,60),
                       new Array( 4, 6,61), new Array(11,10,62),
                       new Array( 2,15,63), new Array( 9,21,64));

        function MD5_F(x, y, z) { return (x & y) | (~x & z); }
        function MD5_G(x, y, z) { return (x & z) | (y & ~z); }
        function MD5_H(x, y, z) { return x ^ y ^ z;          }
        function MD5_I(x, y, z) { return y ^ (x | ~z);       }

        var MD5_round = new Array(new Array(MD5_F, MD5_round1),
                      new Array(MD5_G, MD5_round2),
                      new Array(MD5_H, MD5_round3),
                      new Array(MD5_I, MD5_round4));

        function MD5_pack(n32) {
          return String.fromCharCode(n32 & 0xff) +
             String.fromCharCode((n32 >>> 8) & 0xff) +
             String.fromCharCode((n32 >>> 16) & 0xff) +
             String.fromCharCode((n32 >>> 24) & 0xff);
        }

        function MD5_unpack(s4) {
          return  s4.charCodeAt(0)        |
             (s4.charCodeAt(1) <<  8) |
             (s4.charCodeAt(2) << 16) |
             (s4.charCodeAt(3) << 24);
        }

        function MD5_number(n) {
          while (n < 0)
            n += 4294967296;
          while (n > 4294967295)
            n -= 4294967296;
          return n;
        }

        function MD5_apply_round(x, s, f, abcd, r) {
          var a, b, c, d;
          var kk, ss, ii;
          var t, u;

          a = abcd[0];
          b = abcd[1];
          c = abcd[2];
          d = abcd[3];
          kk = r[0];
          ss = r[1];
          ii = r[2];

          u = f(s[b], s[c], s[d]);
          t = s[a] + u + x[kk] + MD5_T[ii];
          t = MD5_number(t);
          t = ((t<<ss) | (t>>>(32-ss)));
          t += s[b];
          s[a] = MD5_number(t);
        }

        function MD5_hash(data) {
          var abcd, x, state, s;
          var len, index, padLen, f, r;
          var i, j, k;
          var tmp;

          state = new Array(0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476);
          len = data.length;
          index = len & 0x3f;
          padLen = (index < 56) ? (56 - index) : (120 - index);
          if(padLen > 0) {
            data += "\x80";
            for(i = 0; i < padLen - 1; i++)
              data += "\x00";
          }
          data += MD5_pack(len * 8);
          data += MD5_pack(0);
          len  += padLen + 8;
          abcd = new Array(0, 1, 2, 3);
          x    = new Array(16);
          s    = new Array(4);

          for(k = 0; k < len; k += 64) {
            for(i = 0, j = k; i < 16; i++, j += 4) {
              x[i] = data.charCodeAt(j) |
                (data.charCodeAt(j + 1) <<  8) |
                (data.charCodeAt(j + 2) << 16) |
                (data.charCodeAt(j + 3) << 24);
            }
            for(i = 0; i < 4; i++)
              s[i] = state[i];
            for(i = 0; i < 4; i++) {
              f = MD5_round[i][0];
              r = MD5_round[i][1];
              for(j = 0; j < 16; j++) {
            MD5_apply_round(x, s, f, abcd, r[j]);
            tmp = abcd[0];
            abcd[0] = abcd[3];
            abcd[3] = abcd[2];
            abcd[2] = abcd[1];
            abcd[1] = tmp;
              }
            }

            for(i = 0; i < 4; i++) {
              state[i] += s[i];
              state[i] = MD5_number(state[i]);
            }
          }

          return MD5_pack(state[0]) +
             MD5_pack(state[1]) +
             MD5_pack(state[2]) +
             MD5_pack(state[3]);
        }

        function MD5_hexhash(data) {
            var i, out, c;
            var bit128;

            bit128 = MD5_hash(data);
            out = "";
            for(i = 0; i < 16; i++) {
            c = bit128.charCodeAt(i);
            out += "0123456789abcdef".charAt((c>>4) & 0xf);
            out += "0123456789abcdef".charAt(c & 0xf);
            }
            return out;
        }

        // rc2.js
        // RC2 JavaScript port by Igor Afanasyev <afan@mail.ru>
        // Copyright Evernote Corporation, 2008-2009

        var RC2 = {

          keyschedule: function (xkey_string, bits) {

            /* Converting the key string into array of bytes */

            var xkey = xkey_string.split("");
            for (var i = 0; i < xkey.length; i++) {
              xkey[i] = xkey[i].charCodeAt(0);
            }

            /* 256-entry permutation table, probably derived somehow from pi */

            var permute = new Array(
              217,120,249,196, 25,221,181,237, 40,233,253,121, 74,160,216,157,
              198,126, 55,131, 43,118, 83,142, 98, 76,100,136, 68,139,251,162,
               23,154, 89,245,135,179, 79, 19, 97, 69,109,141,  9,129,125, 50,
              189,143, 64,235,134,183,123, 11,240,149, 33, 34, 92,107, 78,130,
               84,214,101,147,206, 96,178, 28,115, 86,192, 20,167,140,241,220,
               18,117,202, 31, 59,190,228,209, 66, 61,212, 48,163, 60,182, 38,
              111,191, 14,218, 70,105,  7, 87, 39,242, 29,155,188,148, 67,  3,
              248, 17,199,246,144,239, 62,231,  6,195,213, 47,200,102, 30,215,
                8,232,234,222,128, 82,238,247,132,170,114,172, 53, 77,106, 42,
              150, 26,210,113, 90, 21, 73,116, 75,159,208, 94,  4, 24,164,236,
              194,224, 65,110, 15, 81,203,204, 36,145,175, 80,161,244,112, 57,
              153,124, 58,133, 35,184,180,122,252,  2, 54, 91, 37, 85,151, 49,
               45, 93,250,152,227,138,146,174,  5,223, 41, 16,103,108,186,201,
              211,  0,230,207,225,158,168, 44, 99, 22,  1, 63, 88,226,137,169,
               13, 56, 52, 27,171, 51,255,176,187, 72, 12, 95,185,177,205, 46,
              197,243,219, 71,229,165,156,119, 10,166, 32,104,254,127,193,173
            );

            if (!bits)
              bits = 1024;

            /* Phase 1: Expand input key to 128 bytes */

            var len = xkey.length;
            for (var i = len; i < 128; i++) {
              xkey[i] = permute[(xkey[i - 1] + xkey[i - len]) & 255];
            }

            /* Phase 2 - reduce effective key size to "bits" */

            var len = (bits + 7) >> 3;
            var i = 128 - len;
            var x = permute[xkey[i] & (255 >> (7 & -bits))];
            xkey[i] = x;
            while (i--) {
              x = permute[x ^ xkey[i + len]];
              xkey[i] = x;
            }

            /* Phase 3 - copy to key array of words in little-endian order */

            var key = new Array(64);
            i = 63;
            do {
              key[i] = (xkey[2 * i] & 255) + (xkey[2 * i + 1] << 8);
            } while (i--);

            return key;
          },

          decrypt_chunk: function (input, xkey) {
            var x76, x54, x32, x10, i;
            x76 = (input.charCodeAt(7) << 8) + input.charCodeAt(6);
            x54 = (input.charCodeAt(5) << 8) + input.charCodeAt(4);
            x32 = (input.charCodeAt(3) << 8) + input.charCodeAt(2);
            x10 = (input.charCodeAt(1) << 8) + input.charCodeAt(0);

            i = 15;
            do {
              x76 &= 65535;
              x76 = (x76 << 11) + (x76 >> 5);
              x76 -= (x10 & ~x54) + (x32 & x54) + xkey[4*i+3];

              x54 &= 65535;
              x54 = (x54 << 13) + (x54 >> 3);
              x54 -= (x76 & ~x32) + (x10 & x32) + xkey[4*i+2];

              x32 &= 65535;
              x32 = (x32 << 14) + (x32 >> 2);
              x32 -= (x54 & ~x10) + (x76 & x10) + xkey[4*i+1];

              x10 &= 65535;
              x10 = (x10 << 15) + (x10 >> 1);
              x10 -= (x32 & ~x76) + (x54 & x76) + xkey[4*i+0];

              if (i == 5 || i == 11) {
                x76 -= xkey[x54 & 63];
                x54 -= xkey[x32 & 63];
                x32 -= xkey[x10 & 63];
                x10 -= xkey[x76 & 63];
              }
            } while (i--);

            var out =
              String.fromCharCode(x10 & 255) +
              String.fromCharCode((x10 >> 8) & 255) +
              String.fromCharCode(x32 & 255) +
              String.fromCharCode((x32 >> 8) & 255) +
              String.fromCharCode(x54 & 255) +
              String.fromCharCode((x54 >> 8) & 255) +
              String.fromCharCode(x76 & 255) +
              String.fromCharCode((x76 >> 8) & 255);

            return out;
          },

          decrypt: function (str, key, bits) {
            var out = "";
            var key_array = this.keyschedule(key, bits);

            while (str.length > 0) {
              var chunk = str.slice(0, 8);
              str = str.slice(8);
              out = out + this.decrypt_chunk(chunk, key_array);
            }

            return out;
          }

        } // end of RC2 namespace

        // utf8.js
        /**
         * Adapted from: http://www.webtoolkit.info/javascript-base64.html
         * License: http://www.webtoolkit.info/licence.html
         * Which reads (2009-08-04):
         * As long as you leave the copyright notice of the original script, or link back to this website, you can use any of the content published on this website free of charge for any use: commercial or noncommercial.
         */
        /**
        *
        *  UTF-8 data encode / decode
        *  http://www.webtoolkit.info/
        *
        **/

        var Utf8 = {

            // public method for url encoding
            encode : function (string) {
                string = string.replace(/\r\n/g,"\n");
                var utftext = "";

                for (var n = 0; n < string.length; n++) {

                    var c = string.charCodeAt(n);

                    if (c < 128) {
                        utftext += String.fromCharCode(c);
                    }
                    else if((c > 127) && (c < 2048)) {
                        utftext += String.fromCharCode((c >> 6) | 192);
                        utftext += String.fromCharCode((c & 63) | 128);
                    }
                    else {
                        utftext += String.fromCharCode((c >> 12) | 224);
                        utftext += String.fromCharCode(((c >> 6) & 63) | 128);
                        utftext += String.fromCharCode((c & 63) | 128);
                    }

                }

                return utftext;
            },

            // public method for url decoding
            decode : function (utftext) {
                var string = "";
                var i = 0;
                var c = c1 = c2 = 0;

                while ( i < utftext.length ) {

                    c = utftext.charCodeAt(i);

                    if (c < 128) {
                        string += String.fromCharCode(c);
                        i++;
                    }
                    else if((c > 191) && (c < 224)) {
                        c2 = utftext.charCodeAt(i+1);
                        string += String.fromCharCode(((c & 31) << 6) | (c2 & 63));
                        i += 2;
                    }
                    else {
                        c2 = utftext.charCodeAt(i+1);
                        c3 = utftext.charCodeAt(i+2);
                        string += String.fromCharCode(((c & 15) << 12) | ((c2 & 63) << 6) | (c3 & 63));
                        i += 3;
                    }

                }

                return string;
            }

        }

        // en-crypt.js
        // EN-Crypt helper logic by Igor Afanasyev <afan@mail.ru>
        // Copyright Evernote Corporation, 2008-2009
        var ENCrypt = {

          EN_RC2_ENCRYPTION_KEYSIZE: 64,

          decrypt: function (base64str, passphrase) {
            // Password is UTF8-encoded before MD5 is calculated.
            // MD5 is used in raw (not hex-encoded) form.

            var str = RC2.decrypt(Base64.decode(base64str), MD5_hash(Utf8.encode(passphrase)), this.EN_RC2_ENCRYPTION_KEYSIZE);

            // First 4 chars of the string is the HEX-representation of the upper-byte of the CRC32 of the string.
            // If CRC32 is valid, we return the decoded string, otherwise return null

            var crc = str.slice(0, 4);
            str = str.slice(4);


            var realcrc = crc32(str) ^ (-1); // Windows client implementation of CRC32 is broken, hence the " ^ (-1)" fix
            realcrc = realcrc >>> 0; // trick to make value an uint before converting to hex
            realcrc = this.d2h(realcrc).substring(0, 4).toUpperCase(); // convert to hex, take only first 4 uppercase hex digits to compare

            if (realcrc == crc) {

              // Get rid of zero symbols at the end of the string, if any

              while ((str.length > 0) && (str.charCodeAt(str.length - 1) == 0))
                str = str.slice(0, str.length - 1);

              // Return Unicode string

              return Utf8.decode(str);

            } else {
              return null;
            }
          },

          d2h: function (d) {
            return d.toString(16);
          }

        } // end of ENCrypt namespace
        ;

        return ENCrypt;
    })(); // evernoteDecrypt


    return function(cipher, length, password, base64_data) {
        var ret;
        if (cipher == "AES") {
            ret = evernoteAesCrypto.decrypt(password, base64_data);
        } else
        if (cipher == "RC2") {
            ret = evernoteDecrypt.decrypt(base64_data, password);
        } else {
            throw "This cipher type is not supported";
        }

        if (ret === null)
            throw "Bad password";

        return ret;
    }

})(); // decrypt
