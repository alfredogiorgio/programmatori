import requests
from pyrogram import Client, filters
from bs4 import BeautifulSoup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx
import tgcrypto
import os
from telegraph import Telegraph
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import redis.asyncio as redis
from keep_alive import keep_alive

telegraph = Telegraph()

load_dotenv()

redisClient = redis.from_url(os.getenv('redis_url'))

app = Client(
    "iProgrammatori",
    api_id=os.getenv('api_id'), api_hash=os.getenv('api_hash'),
    bot_token=os.getenv('bot_token')
)

headers = {'User-Agent': 'My User Agent 1.0'}


@app.on_message(filters.command('start'))
async def start_command_private(app, message):
    await app.send_message(message.from_user.id, text="Ciao! Sono online!")


async def clean():
    for key in await redisClient.keys('*'):

        if requests.get(await redisClient.get(key), headers=headers,
                        allow_redirects=False).status_code != 200:
            await redisClient.delete(key)

    await app.send_message(chat_id=5453376840, text="Finita la pulizia dei file ecc")


async def scrape():
    async with httpx.AsyncClient() as client:
        r = await client.get('https://www.iprogrammatori.it/rss/offerte-lavoro-crawler.xml',
                             headers=headers)

    for job in BeautifulSoup(r.text, 'lxml-xml').find_all('job'):
        idJob = job.find('id').text

        find = await redisClient.get(idJob)
        checked = await redisClient.get(idJob + " last-checked")
        if find is not None or checked is not None:
            break
        if find is None and checked is None:
            titolo = job.find('title').text
            url = job.find('url').text

            async with httpx.AsyncClient() as client:
                a = await client.get(url, headers=headers)

            ok = 1
            for li in BeautifulSoup(a.text, 'lxml-xml').find('ul', 'list-inline info-item-list').find_all('li'):
                label = li.find('label').text
                if label == "Luogo di lavoro:":
                    sede = li.find('label').next_sibling.strip()
                if label == "Compenso lordo:":
                    compenso = li.find('label').next_sibling.strip()
                    if compenso == "Da concordare" or compenso == "":
                        ok = 0
                if label == "Posti disponibili:":
                    posti = li.find('label').next_sibling.strip()
                if label == "Contratto di lavoro:":
                    contratto = li.find('label').next_sibling.strip()
                    if contratto == "Da determinare" or contratto == "":
                        ok = 0
            if ok == 0:
                for oldkey in await redisClient.keys("*last-checked*"):

                    if oldkey.split(" ")[0] != idJob:
                        redisClient.delete(oldkey)
                        await redisClient.set(idJob + " last-checked", url)

            if ok == 1:
                content = job.find('content').text
                company = job.find('company').text if job.find('company') is not None else "Non specificato"
                requirements = job.find('requirements').text if job.find(
                    'requirements') is not None else "Non specificato"
                date = job.find('date').text if job.find(
                    'date') is not None else "Non specificato"

                text = f"""💻 <b>Nuovo annuncio!</b>
        
🔗 <b><a href={url}>{titolo}</a></b>
        
📍 Sede: <b>{sede}</b>
🏢 Azienda: <b>{company}</b>
📄 Contratto: <b>{contratto}</b>
        
💶 Compenso lordo: <b>{compenso}</b>
👥 Posti disponibili: <b>{posti}</b>
        
📅 Data di pubblicazione: <b>{date}</b>"""

                telegraph.create_account(short_name='Programmatori')
                response = telegraph.create_page(title=titolo,
                                                 html_content=f"""<p><b>Descrizione</b></p>
                                                         <p>{content}</p>
                                                         <p><b>Requisiti</b></p>
                                                         <p>{requirements}</p>
                                                         """)
                linktelegraph = response['url']

                message = await app.send_message(-1002097330914, text=text,
                                                 disable_web_page_preview=True)
                annunciobuttons = [
                    [InlineKeyboardButton('Descrizione 📃', url=f"{linktelegraph}")],
                    [InlineKeyboardButton(
                        'Condividi il canale ❗',
                        url="https://telegram.me/share/url?url=https://telegram.me/iProgrammatoriAnnunci&text"
                            "=Unisciti%20per%20ricevere%20notifiche%20su%20nuovi%20annunci%20di%20lavoro"),
                        InlineKeyboardButton('Guadagna 💰', url='t.me/concorsiferrovie/1430')],
                    [InlineKeyboardButton('Condividi su WhatsApp 📱',
                                          url='https://api.whatsapp.com/send?text=Guarda+questo+annuncio+di+lavoro'
                                              '+per+programmatori!+' + message.link)]
                ]

                markupannuncio = InlineKeyboardMarkup(annunciobuttons)

                await app.edit_message_reply_markup(-1002097330914, message_id=message.id,
                                                    reply_markup=markupannuncio)
                await redisClient.set(idJob, url)


sched = AsyncIOScheduler()

sched.add_job(clean, 'cron', hour=23)
sched.add_job(scrape, 'interval', minutes=1)
sched.start()

keep_alive()

app.run()
