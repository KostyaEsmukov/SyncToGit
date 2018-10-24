var gulp = require('gulp');
var uglify = require('gulp-uglify');
var rename = require('gulp-rename');

gulp.task('build', build());
gulp.task('default', build());

function build() {
    function evernoteDecrypt() {
        return script(
            './evernote/decrypt.js',
            '../synctogit/templates/evernote/js/',
            'decrypt.min.js',
        );
    }

    function onenoteJquery() {
        return script(
            './node_modules/jquery/dist/jquery.min.js',
            '../synctogit/templates/onenote/js/',
            'jquery.min.js',
        );
    }

    function onenoteInkml() {
        return script(
            './node_modules/inkmljs/InkMLjs/inkml.js',
            '../synctogit/templates/onenote/js/',
            'inkml.min.js',
        );
    }

    return gulp.parallel(
        evernoteDecrypt,
        onenoteJquery,
        onenoteInkml,
    );
}

function script(src, dest_dir, dest_filename) {
    return gulp.src(src, { sourcemaps: false })
        .pipe(uglify())
        .pipe(rename(dest_filename))
        .pipe(gulp.dest(dest_dir));
}
