*This instructions will install the program and its dependencies in the global environment*

Install the dependencies
```
pip3 install -r requirements.txt
```

Build and install the program
```
python3 -m build
```

The build output can be found in the `dist` directory. Install it as follows, change the file name accordingly
```
pip3 install dist/splinter-0.1.0-py3-none-any.whl
```
