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
