# How to Check Python Version

This document provides instructions on how to check the installed Python version on different operating systems.

## Windows

1.  **Open Command Prompt:** Press `Win + R`, type `cmd`, and press Enter.
2.  **Run Command:** In the Command Prompt, type the following command and press Enter:
    ```bash
    python --version
    ```
3.  **View Output:** The installed Python version will be displayed. If Python is not installed or not added to PATH, you'll see an error message.

## macOS

1.  **Open Terminal:** Press `Cmd + Space` to open Spotlight search, type `Terminal`, and press Enter.
2.  **Run Command:** In the Terminal, type the following command and press Enter:
    ```bash
    python3 --version
    ```
    *Note: macOS often comes with Python 2 pre-installed as `python`. Using `python3` specifically checks for Python 3.*
3.  **View Output:** The installed Python 3 version will be displayed.

## Linux

1.  **Open Terminal:** Press `Ctrl + Alt + T` (this shortcut may vary depending on the Linux distribution).
2.  **Run Command:** In the Terminal, type one of the following commands and press Enter:
    ```bash
    python --version
    ```
    or
    ```bash
    python3 --version
    ```
    *Note: Similar to macOS, `python` might point to an older Python 2. `python3` is generally preferred for checking the Python 3 version.*
3.  **View Output:** The installed Python version will be displayed.

## Verifying if the Version is Recent

To determine if your Python version is recent, you can check the official Python website ([python.org](https://www.python.org/)) for the latest stable release. Generally, versions 3.6 and above are considered relatively recent for most purposes, but it's always a good practice to use one of the latest stable versions if possible, especially for new projects. The environment this check was run in has Python 3.10.17.

# Core Python Libraries Installation

This section provides instructions for installing commonly used Python libraries for web scraping and data handling.

## requests

The `requests` library is an elegant and simple HTTP library for Python, built for human beings.

To install `requests`, run the following command in your terminal:
```bash
pip install requests
```

## beautifulsoup4

Beautiful Soup is a Python library for pulling data out of HTML and XML files. It works with your favorite parser to provide idiomatic ways of navigating, searching, and modifying the parse tree.

To install `beautifulsoup4`, run the following command in your terminal:
```bash
pip install beautifulsoup4
```

## sqlite3

The `sqlite3` module is part of the Python standard library. This means you do not need to install it separately using pip. It provides a lightweight disk-based database that doesn’t require a separate server process and allows accessing the database using a nonstandard variant of SQL.

You can use it directly in your Python scripts by importing it:
```python
import sqlite3
```

# AI and Machine Learning Libraries Installation

This section covers the installation of popular Python libraries for AI and Machine Learning tasks, including Natural Language Processing (NLP), vector databases, and interaction with LLM services.

## transformers

`transformers` provides thousands of pre-trained models to perform tasks on different modalities such as text, vision, and audio.

To install `transformers`, run:
```bash
pip install transformers
```

## sentence-transformers

`sentence-transformers` is a Python framework for state-of-the-art sentence, text, and image embeddings. It relies on `transformers` and `torch`.

To install `sentence-transformers`, run:
```bash
pip install sentence-transformers
```
*Note on PyTorch (`torch`)*: `sentence-transformers` will automatically install `torch`. By default, this might include CUDA support, which can be very large. If you are in a space-constrained environment or do not need GPU support, you can install a CPU-only version of `torch` *before* installing `sentence-transformers`:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install sentence-transformers
```
This was the method used to ensure installation in the environment where this document was prepared.

## scikit-learn

`scikit-learn` is a simple and efficient tool for predictive data analysis, built on NumPy, SciPy, and matplotlib. It's widely used for classical machine learning algorithms.

To install `scikit-learn`, run:
```bash
pip install scikit-learn
```
*(Note: `scikit-learn` might be installed as a dependency of other packages like `sentence-transformers`.)*

## faiss-cpu

`faiss-cpu` is a library for efficient similarity search and clustering of dense vectors. This version is for CPU only.

To install `faiss-cpu`, run:
```bash
pip install faiss-cpu
```
If you have GPU support and want to use it, you can install `faiss-gpu` instead.

## ollama

The `ollama` Python library provides a simple way to integrate and use Ollama models in your Python applications. Ollama allows you to run open-source large language models locally.

To install `ollama`, run:
```bash
pip install ollama
```

# Choosing an IDE or Text Editor

Selecting a good Integrated Development Environment (IDE) or text editor can significantly improve your Python development experience. Here are a few popular choices:

## Visual Studio Code (VS Code)

*   **Description:** VS Code is a free, lightweight, yet powerful source code editor developed by Microsoft. It has excellent Python support through extensions, including features like IntelliSense (code completion), debugging, linting, and Jupyter Notebook support.
*   **Link:** [https://code.visualstudio.com/](https://code.visualstudio.com/)

## PyCharm

*   **Description:** PyCharm is a dedicated Python IDE developed by JetBrains. It offers a comprehensive set of tools for Python development, including advanced debugging, code analysis, testing tools, and support for various web development frameworks. It comes in a free Community edition and a paid Professional edition.
*   **Link:** [https://www.jetbrains.com/pycharm/](https://www.jetbrains.com/pycharm/)

## Sublime Text

*   **Description:** Sublime Text is a sophisticated text editor for code, markup, and prose. It's known for its speed, slick user interface, and powerful features like "Goto Anything," multiple selections, and a customizable plugin system (Package Control) that can be used to add Python-specific functionality.
*   **Link:** [https://www.sublimetext.com/](https://www.sublimetext.com/)

Choosing the right tool often comes down to personal preference and project requirements. Many developers try a few options before settling on their favorite.

# Part 1: Data Acquisition and Database Setup

This section outlines the steps and scripts involved in acquiring the Base de Données Publique des Médicaments (BDPM) data, setting up the SQLite database, and populating it.

## Data Acquisition and Processing Workflow

The data pipeline involves several scripts that should generally be run in the following order:

### 1. Downloading BDPM Source Files (`download_bdpm.py`)

*   **Purpose**: This script initiates the download process for the BDPM dataset. It finds the official download link from `data.gouv.fr`.
*   **Manual Download Required**: Due to restrictions on the server hosting the files, the script cannot download the data automatically. Instead, it will:
    1.  Display the direct URL to the BDPM ZIP file.
    2.  Instruct you to **manually download this ZIP file** using your web browser.
    3.  Ask you to save the downloaded file as `bdpm_data.zip` in the `./data/bdpm_source/` directory (the script will create these directories if they don't exist).
*   **Decompression**: Once you confirm the download by pressing Enter in the script, `download_bdpm.py` will then proceed to decompress the `bdpm_data.zip` file into the `./data/bdpm_source/` directory, making the raw text files available.
*   **Command**:
    ```bash
    python download_bdpm.py
    ```

### 2. Database Initialization (`database_setup.py`)

*   **Purpose**: This script creates the SQLite database file (`medicaments.db`) and defines its schema by creating all necessary tables (`Medicaments`, `Presentations`, `Compositions`, `RCPs`, `Generiques`, `ConditionsPrescriptionDelivrance`).
*   **Usage**: While it can be run standalone, this script is **automatically called** by `import_structured_data.py` before data import begins. Therefore, manual execution is usually not required.
*   **Command (for standalone execution, if needed)**:
    ```bash
    python database_setup.py
    ```

### 3. Importing Structured Data (`import_structured_data.py`)

*   **Purpose**: This script populates the `medicaments.db` database by parsing the decompressed BDPM text files (e.g., `CIS_bdpm.txt`, `CIS_CIP_bdpm.txt`, etc.) located in `./data/bdpm_source/`. It inserts the data into the corresponding tables.
*   **Additional Output**: As part of its process, this script also extracts all unique `code_cis` values found in `CIS_bdpm.txt` and saves them into a file named `unique_cis_codes.json` in the project root. This JSON file is used by the next step (RCP crawling).
*   **Prerequisites**: The BDPM ZIP file must have been downloaded and decompressed by `download_bdpm.py`, so that the raw text files are available in the `./data/bdpm_source/` directory.
*   **Command**:
    ```bash
    python import_structured_data.py
    ```

### 4. Crawling RCP Documents (`crawl_rcp.py`)

*   **Purpose**: This script fetches the "Résumé des Caractéristiques du Produit" (RCP) text for each medication. It uses the `unique_cis_codes.json` file (generated by `import_structured_data.py`) to identify which medications to crawl. The crawled text is stored in the `RCPs` table in the database.
*   **Prerequisites**:
    *   The `medicaments.db` database must exist and be populated (at least with `Medicaments` data).
    *   The `unique_cis_codes.json` file must exist in the project root.
*   **Process**:
    *   The script iterates through the CIS codes and constructs URLs to access the RCP documents on the `base-donnees-publique.medicaments.gouv.fr` website.
    *   It includes a polite delay between requests.
    *   **Resume Feature**: If interrupted, the script can be rerun. It checks for already crawled RCPs in the database and skips them.
    *   **Duration**: This process can take a very long time to complete due to the number of documents and the polite delay between requests.
*   **Command**:
    ```bash
    python crawl_rcp.py
    ```

## Database Schema Overview (`medicaments.db`)

The `medicaments.db` SQLite database stores the imported and crawled data. Key tables include:

*   **`Medicaments`**
    *   **Purpose**: Stores general information about each medication.
    *   **Source**: `CIS_bdpm.txt`.
    *   **Key Fields**: `code_cis` (Primary Key, unique identifier for a medication), `denomination` (name), `forme_pharmaceutique`, `voies_administration`.

*   **`Presentations`**
    *   **Purpose**: Details about specific packaging and commercial presentations of medications.
    *   **Source**: `CIS_CIP_bdpm.txt`.
    *   **Key Fields**: `code_cip13` (Primary Key, unique identifier for a presentation), `code_cis` (Foreign Key to `Medicaments`), `libelle_presentation`, `prix_medicament_euros`, `taux_remboursement`.

*   **`Compositions`**
    *   **Purpose**: Information about the active substances and their dosages in each medication.
    *   **Source**: `CIS_COMPO_bdpm.txt`.
    *   **Key Fields**: `id_composition` (Primary Key), `code_cis` (Foreign Key to `Medicaments`), `denomination_substance`, `dosage_substance`.

*   **`RCPs`** (Résumé des Caractéristiques du Produit)
    *   **Purpose**: Stores the crawled text content of the RCP documents.
    *   **Source**: Web crawling by `crawl_rcp.py`.
    *   **Key Fields**: `code_cis` (Primary Key, Foreign Key to `Medicaments`), `texte_rcp` (full text), `date_derniere_extraction_rcp`.

*   **`Generiques`**
    *   **Purpose**: Information about generic drug groupings.
    *   **Source**: `CIS_GENER_bdpm.txt`.
    *   **Key Fields**: `id_generique` (Primary Key), `code_cis` (Foreign Key to `Medicaments`), `libelle_groupement_generique`.

*   **`ConditionsPrescriptionDelivrance`**
    *   **Purpose**: Stores conditions related to the prescription and delivery of medications.
    *   **Source**: `CIS_CPD_bdpm.txt`.
    *   **Key Fields**: `id_cpd` (Primary Key), `code_cis` (Foreign Key to `Medicaments`), `condition`.

The `.gitignore` file is configured to ignore `*.db` files, so `medicaments.db` will not be committed to the repository. You will need to generate it locally by running the scripts.

## ⚡ Fast GPU Embedding

Recommended: RTX 4060 8 GB – run
```bash
python generate_embeddings.py \
       --batch_size 128 --commit_interval 500
```

Full 450 MB corpus encodes in < 60 min (~9 k rows/s) with model `intfloat/multilingual-e5-base` in FP16.

For even faster (< 40 min) but slightly lower quality, try
```bash
--model intfloat/multilingual-e5-small
```
