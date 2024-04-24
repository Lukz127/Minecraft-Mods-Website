from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
import yaml
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import json
import time
import hashlib

app = FastAPI()
app.mount("/resources", StaticFiles(directory="resources"), name="resources")
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/js", StaticFiles(directory="js"), name="js")

pages = set()
mdPagesDir = "pages/"
cachePath = 'cachedPages/'

if not os.path.exists(cachePath):
    os.mkdir(cachePath)
if not os.path.exists(cachePath+'hashes.json'):
    with open(cachePath+'hashes.json', 'w', encoding='utf-8') as f:
        json.dump({}, f)
if not os.path.exists(cachePath+'pages.txt'):
    with open(cachePath+'pages.txt', 'w', encoding='utf-8') as f:
        f.write('')
with open('html/head.html', encoding='utf-8') as f:
    head = f.read()
with open('html/header.html', encoding='utf-8') as f:
    header = f.read()
with open(cachePath+'hashes.json', encoding='utf-8') as f:
    hashes = json.load(f)
with open(cachePath+'pages.txt', encoding='utf-8') as f:
    for page in f.readlines():
        pages.add(page.strip())
head += '<script type="module" src="https://md-block.verou.me/md-block.js"></script>  <!-- Use the md-block library for markdown-->'
head += '<link rel="stylesheet" type="text/css" href="/css/style.css">                             <!-- Default stylesheet -->'
head += '<script src="js/script.js"></script>                                                      <!-- Default javascript -->'

htmlStart = "<!DOCTYPE html><html lang=\"sk\"><head>"
bodyStart = "</head><body>"
htmlEnd = "</body></html>"

with open('html/index.html', encoding='utf-8') as f:
    index = htmlStart
    index += head
    index += '<link rel="stylesheet" type="text/css" href="/css/index.css">'
    index += "<title>Minecraft Módy</title>"
    index += bodyStart
    index += header
    index += f.read()
    index += htmlEnd
with open('html/404.html', encoding='utf-8') as f:
    err404 = htmlStart
    err404 += head
    err404 += "<title>404 - Stránka sa nenašla</title>"
    err404 += '<link rel="stylesheet" type="text/css" href="/css/404.css">'
    err404 += bodyStart
    err404 += header
    err404 += f.read()
    err404 += htmlEnd


def generateHtml(markdown: str, title: str, background: str, css: list[str] = [], js: list[str] = []):
    data = htmlStart
    data += head
    data += f'<title>{title}</title>'
    for name in css:
        data += f'<link rel="stylesheet" type="text/css" href="css/{name}">'
    for name in js:
        data += f'<script src="js/{name}"></script>'
    data += bodyStart
    if background.startswith("http"):
        data += f'<img src="{background}" alt="" id="backgroundImg">'
    else:
        data += f'<img src="resources/{background}" alt="" id="backgroundImg">'
    data += header
    data += f'<main><md-block>{markdown}</md-block></main>'
    data += htmlEnd
    return data


def parseMd(name: str):
    with open(f'pages/{name}', encoding='utf-8') as f:
        data = f.read()
    dashCount = 0
    startedYaml = False
    yamlStr = ''
    for i, l in enumerate(data):
        if l == '-':
            dashCount += 1
        else:
            dashCount = 0
        if l == '-' and len(data) > i+2 and data[i+1] == '-' and data[i+2] == '-' and startedYaml:
            data = data[i+3:]
            break
        if startedYaml:
            yamlStr += l
        elif dashCount == 3:
            startedYaml = True
    settings = yaml.safe_load(yamlStr)
    if 'customCSS' not in settings:
        settings['customCSS'] = []
    if 'customJS' not in settings:
        settings['customJS'] = []
    return settings, data


def generateMd(name: str):
    settings, markdown = parseMd(name)
    data = generateHtml(markdown, settings['title'], settings['background'], settings['customCSS'], settings['customJS'])
    return data, settings['path']


def hashMdFile(name: str):
    time.sleep(0.01)  # A little bit of delay to fix it.
    with open(mdPagesDir+name, 'rb') as f:
        h = hashlib.sha256(f.read(), usedforsecurity=False).hexdigest()
    return h


def cacheMd(name: str):
    print(f'Caching: {name}')
    try:
        html, path = generateMd(name)
        pages.add(path)
        with open(cachePath+os.path.splitext(name)[0]+'.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print('Caching successful!')
        return 0
    except TypeError:
        print(f'Caching failed: {name}')
        return 1


def checkMdFile(name: str):
    h = hashMdFile(name)
    if name in hashes and hashes[name] == h and os.path.exists(cachePath+os.path.splitext(name)[0]+'.html'):
        return 1
    hashes[name] = h
    if cacheMd(name):
        hashes[name] = None
    return 0


@app.on_event("startup")
async def setup():
    for fileName in os.listdir('pages/'):
        checkMdFile(fileName)
    observer.start()


@app.on_event("shutdown")
async def setup():
    with open(cachePath+'pages.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(page for page in pages))
    with open(cachePath+'hashes.json', 'w', encoding='utf-8') as f:
        json.dump(hashes, f)
    observer.stop()


# Handler for not found pages
@app.exception_handler(404)
async def not_found(request: Request, exc: HTTPException):
    if request.url.path in pages:
        return FileResponse(cachePath+request.url.path+'.html', media_type='text/html')
    return Response(err404, media_type="text/html")


@app.get("/", response_class=HTMLResponse)
async def read_root():
    return Response(index, media_type="text/html")


class PageChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory or not event.src_path.startswith(str(mdPagesDir)):
            return
        checkMdFile(os.path.basename(event.src_path))


# Create an observer to monitor file system events
observer = Observer()
observer.schedule(PageChangeHandler(), str(mdPagesDir))
