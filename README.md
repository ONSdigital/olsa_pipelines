# onslocal_internal

## Contact
This repository was developed and is maintained by OLSA.

## Project structure

```text
onslocal_internal/
├── functions/ <- Folder containing general use functions
├── pipeline/  <- Folder containing pipeline code
├── .gitignore <- Contains a list of file types that git will ignore
├── CODEOWNERS <- Contains list of code contributors
├── index.md   <- Test file to display documentation (may be developed in future)
├── LICENSE    <- License for the project
├── README.md  <- The file you are currently reading
├── requirements.txt <- File containing project dependencies
```

Contents of folders will be detailed by the README.md files within that directory.

## Setup

* This project was developed using Python 3.12.3
* Required Python libraries are listed in `requirements.txt`

### Installation

Navigate to the folder where you wish to clone this git repository and run:

```
git clone https://github.com/ONSdigital/onslocal_internal.git
```

IDEs such as Pycharm can make virtual environment set up easier, however, to manually set up a virtual environment, 
enter the cloned folder and initialise a virtual environment using:

```
cd onslocal_internal
python -m venv venv
```

To activate the virtual environment:

* On Windows

```
venv\Scripts\activate
```

* On MacOS/Linux

```
source venv/bin/activate
```

Then download the requirements in the virtual environment using
To install it with `pip`, use:
```
pip install -r requirements.txt
```

The desired script can then be ran using:

```
python <script-name>/main.py
```
