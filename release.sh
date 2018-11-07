#!/bin/bash

if [ -z "$1" ]; then
    echo "[x] Indicate as command line parameter the new version number."
    echo "    Last version: $(git tag | tail -1)"
    exit 1
fi

if [ -z "$VIRTUAL_ENV" ]; then
    echo "[x] You should be in pipenv's virtual environment in order to run this."
    echo "    Run again, but from pipenv run or pipenv shell."
    exit 3
fi

VERSION="$1"
if git describe --exact-match "$VERSION" >/dev/null 2>/dev/null; then
    echo "[!] Version already tagged."
    if [ "$(git describe --exact-match 2>/dev/null)" != "$VERSION" ]; then
        echo "[x] Current Git tree and index do not match the version you mean to package."
        echo "    Check out this version, then re-run the script."
        exit 2
    fi
else
    BRANCH_RELEASE="release-$VERSION"
    BRANCH_CURRENT=$(git branch | awk '$1 == "*"{print $2}')
    BRANCH_NEW=""
    if [ $BRANCH_CURRENT != $BRANCH_RELEASE ]; then
        echo "[*] Set up release branch."
        git branch "$BRANCH_RELEASE" && \
            git checkout "$BRANCH_RELEASE" && \
            git push --set-upstream origin "$BRANCH_RELEASE" || \
            exit $?
        BRANCH_NEW="$BRANCH_RELEASE"
    fi

    if ! grep -q "version='$VERSION'," setup.py; then
        echo "[*] Bump version in setup.py"
        TEMP=$(mktemp) && \
            sed -e "s/version='.*',/version='$VERSION',/" setup.py >"$TEMP" && \
            mv "$TEMP" setup.py || \
            exit $?
        if ! (git add setup.py && git commit --message="Bump version to $VERSION" && git push); then
            echo "[x] Unable to commit and push the version bump"
            X=$?
            git checkout setup.py
            exit $X
        fi
    fi

    echo "[*] Make annotated tag for the new release"
    git tag --annotate --sign "$VERSION" || exit $?
    if ! git push --tags; then
        X=$?
        echo "[x] Unable to push the new tag; removing"
        git tag --delete "$VERSION"
        exit $X
    fi
fi

echo "[*] Generate distribution files"
if ! python setup.py sdist bdist_wheel; then
    X=$?
    echo "[x] Failure in distribution file generation"
    exit $X
fi

echo "[*] Upload to PyPI"
if ! twine upload "dist/*$VERSION*"; then
    X=$?
    echo "[x] Failure during upload"
    exit $X
fi

if [ -n "$BRANCH_NEW" ]; then
    echo "[!] You should file a PR for branch $BRANCH_NEW and merge it to master."
fi
