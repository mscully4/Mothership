#! /bin/bash

set -e

# Check if at least one argument is provided
if [ "$#" -ne 1 ]; then
    echo "Invalid number of arguments provided"
    exit 1
fi

first_argument=$1

# Switch statement based on the first positional argument
case $1 in
    cdk)
        echo "Building for CDK"

        tsc
        cdk synth --quiet
        cdk list
        ;;
    py)
        echo "Building for Python"

        echo "Running Black"
        python3 -m black ./src
        printf "\n"

        echo "Running Flake8"
        python3 -m flake8 ./src
        printf "\n"

        echo "Running Mypy"
        python3 -m mypy ./src
        ;;
    *)
        echo "Invalid argument: $1"
        exit 1
        ;;
esac
