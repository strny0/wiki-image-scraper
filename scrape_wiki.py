import asyncio, re, aiofiles, os
from aiohttp import ClientSession
from typing import Iterable, Tuple
from bs4 import BeautifulSoup
from pathlib import Path
from functools import reduce
from tqdm import tqdm
import shutil
import argparse

def LoadLinks(filepath: str) -> set:
    with open(filepath, 'r', encoding='utf-8') as fp:
        return set(fp.read().replace('\r', '').split('\n'))

async def gatherer_worker(links: Iterable[str], html_parseing_queue: asyncio.Queue, session: ClientSession, ignored_ext: list =[], existing_files: list =[]):
    for url in links:
        filename_url_list = await find_images_in_url(url, session, ignored_ext=ignored_ext)
        for filename, url in filename_url_list:
            if filename in existing_files: continue
            await html_parseing_queue.put((filename, url))
    await html_parseing_queue.put('kill')

async def find_images_in_url(url: str, session: ClientSession, img_src_regex_pattern: str = r'href="[^"]+', ignored_ext: list = []) -> list:
    link_name = url.rsplit('/',1)[1]
    async with session.get(url) as r:
        r.raise_for_status()
        site_html = await r.content.read()
    soup = BeautifulSoup(site_html, 'html.parser')
    img_src_regex = re.compile(img_src_regex_pattern)
    img_tags = [img_src_regex.search(str(find)).group() for find in soup.find_all(class_="image")]
    img_filepaths = [i[6:] for i in img_tags]
    img_filenames = [(link_name,item.rsplit('.',1)[1].lower(), item) for i, item in enumerate(img_filepaths)]
    link_filename_list = []
    for idx, (link_name, ext, url) in enumerate(img_filenames, start = 1):
        if ext in ignored_ext: continue
        link_filename_list.append((f"{link_name}_{idx}.{ext}",url))
        
    return link_filename_list

async def wiki_worker(queue: asyncio.Queue, session: ClientSession, output_folder: str):
    while True:
        try:
            filename_url_image = await queue.get()
            if filename_url_image == "kill":
                await queue.put('kill')
                break
            #print(f"received: {image}")
            found_img_list = await parse_image_urls(filename_url_image, session)
            await download_images(found_img_list, output_folder, session)
        except:
            pass
        finally:
            queue.task_done()
        

async def parse_image_urls(found_image_url: tuple, session: ClientSession, regex_pat= r'upload.wikimedia.org/.+" ', base_link = "https://en.wikipedia.org") -> list:
    found_img_tags=[]
    filename, url = found_image_url
    async with session.get(f'{base_link}/{url}') as r:
        site_html = await r.content.read()
    soup = BeautifulSoup(site_html, 'html.parser')
    found_img_tags.append(soup.find_all(class_='internal'))
    regex = re.compile(regex_pat)
    img_src_url = tuple(regex.findall(str(f)) for f in found_img_tags)
    img_src_url = reduce(list.__add__, (items for items in img_src_url))
    return (filename, "https://"+img_src_url[0][:-2])

async def download_images(parsed_image_urls: Tuple[str,str], folder:str, session: ClientSession, chunk = 1024):
    filename, url = parsed_image_urls
    async with session.get(url) as r:
        with tqdm(total=r.content_length, desc=filename, leave=False, unit='b', unit_divisor=1024, unit_scale=True, dynamic_ncols=True) as pbar:
            async with aiofiles.open(f'{folder}/{filename}.tmp', 'wb') as writer:
                async for chunk in r.content.iter_chunked(chunk):
                    await writer.write(chunk)
                    pbar.update(len(chunk))
    shutil.move(f'{folder}/{filename}.tmp',f'{folder}/{filename}')

async def run_all(links, folder, extensions_filter, workers_count):
    queue = asyncio.Queue()
    os.makedirs(folder, exist_ok=True)
    files_in_folder = os.listdir(folder)
    async with ClientSession() as session:
        gatherer = gatherer_worker(links, queue, session, ignored_ext=extensions_filter, existing_files = files_in_folder)
        workers = [asyncio.create_task(wiki_worker(queue, session, folder)) for i in range(workers_count)]
        await asyncio.gather(gatherer, *workers)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('urls', type=str, help="A text file with (en) wikipedia urls")
    parser.add_argument('output', type=str, help= "Download folder")
    parser.add_argument('-w','--workers',default=5, type=int, help= "Number of concurrent downloads.")
    parser.add_argument('-e', '--exclude', nargs='*', type=str, default=[], help="Exclude files with certain extensions, ex. -e svg png")
    known_args, unknown_args = parser.parse_known_args()
    if unknown_args:
        print(f"Entered unknown args: {unknown_args}")
        quit(1)

    base_folder = Path(known_args.output).resolve().as_posix()
    links_file = Path(known_args.links).resolve().as_posix()
    links = LoadLinks(links_file)
    
    try:
        asyncio.get_event_loop().run_until_complete(run_all(links, base_folder, known_args.exclude, known_args.workers))
    except KeyboardInterrupt:
        asyncio.get_event_loop().stop()
        print("\n"*known_args.workers)
        print("Cancelling... (you may resume the download with the same command)")
    
