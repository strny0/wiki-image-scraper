import asyncio, aiohttp, re, aiofiles, os
from typing import Iterable, Tuple
from bs4 import BeautifulSoup
from pathlib import Path
from functools import reduce
import tqdm, shutil, sys

def LoadLinks(path2file: str) -> set:
    with open(path2file, 'rb') as reader:
        links2scrape = reader.read().decode('utf-8').split('\n')
    return set(links2scrape)

async def gatherer_worker(links: Iterable[str], parser_queue: asyncio.Queue, session: aiohttp.ClientSession, ext_filter=[], existing_files=[]):
    for url in links:
        output = await gather_links(url, session, ext_filter=ext_filter)
        for o in output:
            #print(f"passing: {o}")
            if o[0] in existing_files:
                continue
            await parser_queue.put(o)
    await parser_queue.put('kill')

async def gather_links(link,session, regex = 'href="[^"]+', ext_filter=[]) -> tuple:
    link_name = link.rsplit('/',1)[1]
    async with session.get(link) as r:
        r.raise_for_status()
        site_html = await r.content.read()
    soup = BeautifulSoup(site_html, 'html.parser')
    rgx= re.compile(regex)
    found = [rgx.search(str(find)).group() for find in soup.find_all(class_="image")]
    found2 = [i[6:] for i in found]
    pre_output = [(link_name,item.rsplit('.',1)[1].lower(), item) for i, item in enumerate(found2)]
    output = []
    index = 1
    for link_name, ext, link in pre_output:
        if ext in ext_filter:
            continue
        output.append((f"{link_name}_{index}.{ext}",link))
        index += 1 
    return output

async def wiki_worker(queue: asyncio.Queue, session: aiohttp.ClientSession, folder: str):
    while True:
        try:
            image = await queue.get()
            if image == "kill":
                await queue.put('kill')
                break
            #print(f"received: {image}")
            download_object = await parse_links(image,session)
            await download_images(download_object, folder, session)
        except:
            pass
        finally:
            queue.task_done()
        

async def parse_links(found_image,session, regex='upload.wikimedia.org/.+" ', base_link = "https://en.wikipedia.org") -> list:
    found2=[]
    async with session.get(f'{base_link}/{found_image[1]}') as r:
        site2_html = await r.content.read()
        soup2 = BeautifulSoup(site2_html, 'html.parser')
        found2.append(soup2.find_all(class_='internal'))
    rgx2 = re.compile(regex)
    found3 = tuple(rgx2.findall(str(f)) for f in found2)
    found3 = reduce(list.__add__, (items for items in found3))
    return (found_image[0], "https://"+found3[0][:-2])

async def download_images(parsed_image_url: Tuple[str,str], folder:str, session, chunk_size = 1024):
    filename = parsed_image_url[0]
    async with session.get(parsed_image_url[1]) as r:
        #print(f"downloading {filename}")
        with tqdm.tqdm(total=r.content_length, desc=filename, leave=False, unit='b', unit_divisor=1024, unit_scale=True, dynamic_ncols=True) as pbar:
            async with aiofiles.open(f'{folder}/{filename}.tmp', 'wb') as writer:
                async for chunk in r.content.iter_chunked(chunk_size):
                     await writer.write(chunk)
                     pbar.update(len(chunk))
    shutil.move(f'{folder}/{filename}.tmp',f'{folder}/{filename}')

async def run_all(links, folder, extensions_filter):
    queue = asyncio.Queue()
    try:
        os.mkdir(folder)
    except:
        pass
    files_in_folder = os.listdir(folder)
    async with aiohttp.ClientSession() as session:
        gatherer = gatherer_worker(links,queue,session, ext_filter=extensions_filter, existing_files = files_in_folder)
        workers = [asyncio.create_task(wiki_worker(queue, session, folder)) for i in range(5)]
        await asyncio.gather(gatherer, *workers)

if __name__ == "__main__":
    base_folder = Path('./wiki-images').resolve().as_posix()
    links_file = Path(sys.argv[1]).resolve().as_posix()
    exclude_ext = ['svg', 'svg','gif', 'png']
    links = LoadLinks(links_file)
    try:
        asyncio.get_event_loop().run_until_complete(run_all(links,base_folder, exclude_ext))
    except KeyboardInterrupt:
        asyncio.get_event_loop().stop()
        print("\n\n\n\n\n")
        print("Cancelling... (you may resume at any time)")
    

