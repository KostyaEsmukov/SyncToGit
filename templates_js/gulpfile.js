var gulp = require('gulp');
var uglify = require('gulp-uglify');
var rename = require('gulp-rename');

gulp.task('build', build());
gulp.task('default', build());

function build() {
    function scriptEvernote() {
        return script(
            './evernote/decrypt.js',
            '../synctogit/templates/evernote/js/',
            'decrypt.min.js',
        );
    }

    return gulp.parallel(
        scriptEvernote,
    );
}

function script(src, dest_dir, dest_filename) {
    return gulp.src(src, { sourcemaps: false })
        .pipe(uglify())
        .pipe(rename(dest_filename))
        .pipe(gulp.dest(dest_dir));
}
