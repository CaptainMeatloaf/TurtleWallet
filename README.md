# turtle-wallet

A GUI wallet for [TurtleCoin](https://github.com/turtlecoin/turtlecoin), based on `walletd`.

## Getting Started

To get started, install the prerequisites as detailed below, then look at the "Running" section

### Prerequisites

This program is written using Python 2.7.

It requires [PyGObject](https://pygobject.readthedocs.io/en/latest/getting_started.html) to be installed.

It also has the following prerequisites, installed via `pip`

* psutil
* requests
* tzlocal
* enum34

__WINDOWS__: PyGObject instructions for Windows requires MSYS to be running. Some of the python packages are not permitted on this
platform and additionally it adds some overhead to development. This [installer](https://sourceforge.net/projects/pygobjectwin32/) installs the required GTK libs natively.
The installer contains a wizard which will guide you through selecting which python environment and from there you have options of which libs
you want installed: look for the GTK and glade options.

### Running

**Note: opening your wallet with `walletd` renders it no longer readable by `simplewallet`. Please make a backup, as always.**

Getting this wallet running is easy.

* Set TURTLE_HOME to the directory containing walletd __OR__ place a copy of walletd in the current working directory.
* Alternatively, you may still run walletd separately, if you use a custom URI:
   - `export DAEMON_PORT` - default is 8070
   - `export DAEMON_HOST` - default is http://127.0.0.1
   - An example launch command for `walletd` that means you do not have to start the daemon (ie, `Turtlecoind`) alongside it would be as follows:
        ```
        ./walletd -w <wallet file name> -p <wallet password> --local --rpc-password <a password you choose for rpc>
        ```
Having installed the prerequisites, you can start it from a terminal:

```
# WINDOWS users would use SET instead of export here
export TURTLE_HOME=/users/myuser/TurtleCoin-linux/
python start.py -w <wallet file location> -p <wallet password>
```

And everything should start up as intended, provided you installed everything correctly.


## Building an executable

This project can be built with `pyinstaller`, if required. This will most likely be the case for full releases.

## Contributing

Feel free to submit a pull request, it will be reviewed and feedback given.

## Authors

* **CodIsAFish** - *Initial work* - [CaptainMeatloaf](https://github.com/CaptainMeatloaf)

## License

This project is licensed under the LGPLv3 License.

## Acknowledgments

* RockSteady, for pointing me at the right docs
