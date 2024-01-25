import requests
from pyrogram import Client, filters
from bs4 import BeautifulSoup
import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx
import asyncio
import tgcrypto
import os
from telegraph import Telegraph
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

telegraph = Telegraph()

sched = AsyncIOScheduler()

load_dotenv()

api_id = os.getenv('api_id')
api_hash = os.getenv('api_hash')
bot_token = os.getenv('bot_token')

app = Client(
    "iProgrammatori",
    api_id=api_id, api_hash=api_hash,
    bot_token=bot_token
)


@app.on_message(filters.command('start'))
async def start_command_private(app, message):
    await app.send_message(message.from_user.id, text="Ciao! Sono online!")


def clean():
    print("iniziamo la pulizia!")

    f = open("newJobs.json")
    data = json.load(f)
    jobCheckList = []
    for job in data:

        headers = {
            'User-Agent': 'My User Agent 1.0'
        }

        response = requests.get(job, headers=headers, allow_redirects=False)
        if response.status_code == 200:
            jobCheckList.append(job)
    with open("newJobs.json", 'w') as f:
        json.dump(jobCheckList, f, indent=4)

    app.send_message(-1005453376840, text="Iniziata la pulizia dei file ecc")


async def scrape():
    print("andato")
    headers = {
        'User-Agent': 'My User Agent 1.0'
    }

    async with httpx.AsyncClient() as client:
        r = await client.get('https://www.iprogrammatori.it/rss/offerte-lavoro-crawler.xml', headers=headers)
    soup = BeautifulSoup(r.text, 'lxml-xml')

    jobs = soup.find_all('job')

    f = open('newJobs.json')
    data = json.load(f)

    trovato = 0
    for job in jobs:

        for jobJson in data:
            if job.find('url').text == jobJson:
                print(
                    "l'ultimo annuncio è già presente quindi non aggiungo nulla al file json")
                trovato = 1
                break

        if trovato == 1:
            break
        if trovato == 0:
            jobJson = {}

            jobJson['id'] = job.find('id').text
            jobJson['title'] = job.find('title').text
            jobJson['url'] = job.find('url').text

            async with httpx.AsyncClient() as client:
                a = await client.get(job.find('url').text, headers=headers)
            soupA = BeautifulSoup(a.text, 'lxml-xml')

            ul = soupA.find('ul', 'list-inline info-item-list')
            lis = ul.find_all('li')

            stop = 0
            for li in lis:
                label = li.find('label').text
                if label == "Luogo di lavoro:":
                    jobJson['city'] = li.find('label').next_sibling.strip()
                if label == "Compenso lordo:":
                    jobJson['compenso'] = li.find('label').next_sibling.strip()
                    if jobJson['compenso'] == "Da concordare":
                        stop = 1
                if label == "Posti disponibili:":
                    jobJson['posti'] = li.find('label').next_sibling.strip()
                if label == "Contratto di lavoro:":
                    jobJson['jobtype'] = li.find('label').next_sibling.strip()
                    if jobJson['jobtype'] == "Da determinare":
                        stop = 1
            if stop == 0:
                jobJson['content'] = job.find('content').text

                try:
                    jobJson['company'] = job.find('company').text
                except:
                    jobJson['company'] = "Non specificato"

                try:
                    jobJson['requirements'] = job.find('requirements').text
                except:
                    jobJson['requirements'] = "Non specificato"

                try:
                    jobJson['date'] = job.find('date').text.encode(
                        'iso-8859-1').decode('utf-8', errors='ignore')
                except:
                    jobJson['date'] = "Non specificato"

                data.append(job.find('url').text)

                text = f"""💻 <b>Nuovo annuncio!</b>
    
🔗 <b><a href={jobJson['url']}>{jobJson['title']}</a></b>
    
📍 Sede: <b>{jobJson['city']}</b>
🏢 Azienda: <b>{jobJson['company']}</b>
📄 Contratto: <b>{jobJson['jobtype']}</b>
    
💶 Compenso lordo: <b>{jobJson['compenso']}</b>
👥 Posti disponibili: <b>{jobJson['posti']}</b>
    
📅 Data di pubblicazione: <b>{jobJson['date']}</b>"""

                telegraph.create_account(short_name='Programmatori')
                response = telegraph.create_page(f'{jobJson["title"]}',
                                                 html_content=f"""<p><b>Descrizione</b></p>
                                                 <p>{jobJson['content']}</p>
                                                 <p><b>Requisiti</b></p>
                                                 <p>{jobJson['requirements']}</p>
                                                 """)
                linktelegraph = response['url']

                annunciobuttons = [[
                    InlineKeyboardButton(
                        'Condividi il canale ❗',
                        url="https://telegram.me/share/url?url=https://telegram.me/iProgrammatoriAnnunci&text=Unisciti%20per%20ricevere%20notifiche%20su%20nuovi%20annunci%20di%20lavoro"
                    ), InlineKeyboardButton('Condividi su WhatsApp 📱',
                                            url='https://api.whatsapp.com/send?text=Guarda+questo+annuncio+di+lavoro+per+programmatori!')
                ], [InlineKeyboardButton('Descrizione 📃', url=f"{linktelegraph}")], [
                    InlineKeyboardButton('Guadagna 💰', url='t.me/concorsiferrovie/1430')]]

                markupannuncio = InlineKeyboardMarkup(annunciobuttons)

                await app.send_message(-1002097330914, text=text, reply_markup=markupannuncio,
                                       disable_web_page_preview=True)

                with open('newJobs.json', 'w') as file:
                    json.dump(data, file, indent=4)


app.start()

sched.add_job(clean, 'interval', hours=24)
sched.add_job(scrape, 'interval', seconds=30)
sched.start()

try:
    asyncio.get_event_loop().run_forever()
except (KeyboardInterrupt, SystemExit):
    pass
