# Simple wiki image downloader

This simple pyton script quickly downloads all images from a wikipedia article into a folder.

## Quickstart

Windows:

Download the source code from github or with command `git clone https://github.com/strny0/wiki-image-scraper`

Install dependencies

```powershell
pip install -r requirements.txt
```

Run the program

```powershell
py scrape_wiki.py links.txt ./output
```

Linux/Mac:

Download the source code from github or with command `git clone https://github.com/strny0/wiki-image-scraper`

Install dependencies

```bash
pip3 install -r requirements.txt
```

Run the program

```bash
python3 scrape_wiki.py links.txt ./output
```

## Input file

Exammple file with urls

file: links.txt
contents:
```txt
https://en.wikipedia.org/wiki/Hạ_Long_Bay
https://en.wikipedia.org/wiki/Victoria_Falls
https://en.wikipedia.org/wiki/Great_Zimbabwe
```

## License

MIT
