# This example requires the 'message_content' privileged intent to function.

import asyncio
from api import search
import discord
import youtube_dl

from discord.ext import tasks, commands

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url_playlist = []
        self.playlist=[]
        self.current_url = 'None'
        self.current_name = 'None'
        self.finding = False
        self.control = self.after_controll

    @tasks.loop(seconds=60.0)
    async def auto_disconnect(self,ctx):
        if not self.finding and self.current_name == 'None' and self.current_url == 'None' and ctx.voice_client is not None:
            await ctx.send('auto disconnect from voice channel')
            await ctx.voice_client.disconnect()

    @commands.command(name="채널접속")
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        """Joins a voice channel"""
        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()   

    @commands.command(name="검색")
    async def search_check(self,ctx,*,query): # waiting for message here

        self.finding = True
        """유튜브를 통해 영상 검색처리하기."""

        if query.startswith('https://www.youtube.com') or query.startswith('https://youtu.be'):
            url_search_result = await search(query)

            if len(url_search_result) == 0:
                await ctx.send("search result empty")
                return

            item = url_search_result[0]
            self.url_playlist.append(item['value'])
            self.playlist.append(item['name'])

            if not ctx.voice_client.is_playing():
                await self.after(ctx)
            else :
                await ctx.send(f"{item['name']} : playlist added")
            self.finding = False

        else :
        
            url_search_result = await search(query)

            if len(url_search_result) == 0:
                await ctx.send("search result empty")
                return

            result = ''

            tmp = 0
            for item in url_search_result:
                result = result +str(tmp)+" : " + str(item['name']) + "\n"
                tmp = tmp+1
            result = result + f"**{ctx.author}**, send anything in 60 seconds!"
            await ctx.send(result)

            def check(m: discord.Message):  # m = discord.Message.
                return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and m.content.isdigit()
                # checking author and channel, you could add a line to check the content.
                # and m.content == "xxx"
                # the check won't become True until it detects (in the example case): xxx
                # but that's not what we want here.
                # Waiting for a number?
                # str has a method called "isdigit" that returns True -
                # - if the string is a number
                # so.. we can add something like following in the check:
                # m.content.isdigit()
                # and now the won't become True
                # until the content is all numbers, no letters.

            try:
                #              event = on_message without on_
                msg = await self.bot.wait_for('message', check = check, timeout = 20.0)
                # msg = discord.Message
            except asyncio.TimeoutError: 
                # at this point, the check didn't become True, let's handle it.
                await ctx.send(f"**{ctx.author}**, you didn't send any message that meets the check in this channel for 20 seconds..")
                url_search_result = []
                self.finding = False
                return
            else:
                # at this point, the check has become True and the wait_for has done its work, now we can do ours.
                # we could also do things based on the message content here, like so
                # if msg.content == "this is cool":
                #    return await ctx.send("wait_for is indeed a cool method")

                item = url_search_result[int(msg.content)]
                self.url_playlist.append(item['value'])
                self.playlist.append(item['name'])
                if not ctx.voice_client.is_playing():
                    await self.after(ctx)
                else :
                    await ctx.send(f"{item['name']} : playlist added")
                self.finding = False
    
    async def play_song(self,ctx):

        print(self.current_name)

        async with ctx.typing():
            player = await YTDLSource.from_url(self.current_url, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: self.control(ctx,e))

        await ctx.send(f'Now playing: {player.title}')

    def after_controll(self,ctx,error):
        fut = asyncio.run_coroutine_threadsafe(self.after(ctx),self.bot.loop)
        try:
            fut.result()
        except:
            print('somting wrong')
            pass

    def repeat_controll(self,ctx,error):
        fut = asyncio.run_coroutine_threadsafe(self.play_song(ctx),self.bot.loop)
        try:
            fut.result()
        except:
            print('somting wrong')
            pass

    async def after(self, ctx):

        if len(self.url_playlist) != 0 and len(self.playlist) !=0 :
            self.current_url = self.url_playlist.pop(0)
            self.current_name = self.playlist.pop(0)
            await self.play_song(ctx)
        elif len(self.url_playlist) == 0 and len(self.playlist) == 0:
            self.current_name = 'None'
            self.current_url = 'None'
            await ctx.send('playlist empty')

    @commands.command(name="반복")
    async def loop_play(self,ctx):

        if self.control == self.repeat_controll:
            await ctx.send("loop play already set.")
            return

        self.control = self.repeat_controll
        await ctx.send("loop play set")

    @commands.command(name="반복해제")
    async def after_play(self,ctx):

        if self.control == self.after_controll:
            await ctx.send("normal play already set.")
            return

        self.control = self.after_controll
        await ctx.send("normal play set")

    @commands.command(name="대기열")
    async def check_playlist(self,ctx):
        if self.current_name != "None" and len(self.playlist) !=0 and len(self.url_playlist) !=0 :
            result = f'current play : {self.current_name} \n next : \n'

            tmp = 0
            for name in self.playlist:
                result = result + f'{tmp} : {name} \n'
                tmp = tmp + 1

            await ctx.send(result)
        else:
            await ctx.send(f'current play : {self.current_name} \n playlist empty')

    @commands.command(name = "재생")
    async def stream(self, ctx):
        """Streams from a url (same as yt, but doesn't predownload)"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        await self.after(ctx)
    
    @commands.command(name="스킵")
    async def skip(self,ctx):

        if not ctx.voice_client.is_playing():
            await ctx.send('there is nothing playing now')
            return
        if self.control == self.repeat_controll:

            if len(self.url_playlist) != 0 and len(self.playlist) !=0 :
                print("skip_test")
                self.current_url = self.url_playlist.pop(0)
                self.current_name = self.playlist.pop(0)
                print(self.current_name)
                await ctx.send('skiped music')
                await ctx.voice_client.stop()
                await self.play_song(ctx)
                return
            elif len(self.url_playlist) == 0 and len(self.playlist) == 0:
                self.current_name = 'None'
                self.current_url = 'None'
                await ctx.send('playlist empty')
                await ctx.voice_client.stop()
                return
        else :
            await ctx.send('skiped music')
            await ctx.voice_client.stop()
            await self.after(ctx)

    @commands.command(name="일시정지")
    async def pause(self,ctx):

        if not ctx.voice_client.is_playing():
            await ctx.send('there is nothing playing now')
            return

        await ctx.voice_client.pause()

    @commands.command(name="다시시작")
    async def resume(self,ctx):

        if ctx.voice_client.is_playing():
            await ctx.send('there is nothing pauseing now')
            return

        await ctx.voice_client.resume()

    @commands.command(name="볼륨")
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

    @commands.command(name="떠나기")
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        await ctx.voice_client.disconnect()

    @search_check.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
