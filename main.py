import asyncio
import functools
import itertools
import math
import random
import os 
import discord
import youtube_dl
from async_timeout import timeout
from discord.ext import commands
from itertools import cycle

status = cycle(['.help', 'Made by Pedrrro#3237'])

# Silence useless bug reports messages

youtube_dl.utils.bug_reports_message = lambda: ''


class VoiceError(Exception):
    pass


class YTDLError(Exception):
    pass


class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'source_address': '0.0.0.0',
    }

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, ctx: commands.Context, source: discord.FFmpegPCMAudio, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data

        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        date = data.get('upload_date')
        self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.tags = data.get('tags')
        self.url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')
        self.stream_url = data.get('url')

    def __str__(self):
        return '**{0.title}** por **{0.uploader}**'.format(self)

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError('Não pude achar nada compativel com `{}`'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        webpage_url = process_info['webpage_url']
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError('Couldn\'t fetch `{}`'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError('Não consegui achar resultados para `{}`'.format(webpage_url))
        
        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

    @classmethod
    async def search_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        channel = ctx.channel
        loop = loop or asyncio.get_event_loop()

        cls.search_query = '%s%s:%s' % ('ytsearch', 10, ''.join(search))

        partial = functools.partial(cls.ytdl.extract_info, cls.search_query, download=False, process=False)
        info = await loop.run_in_executor(None, partial)

        cls.search = {}
        cls.search["title"] = f'Resultados para :\n**{search}**'
        cls.search["type"] = 'rich'
        cls.search["color"] = 7506394
        cls.search["author"] = {'Nome': f'{ctx.author.name}', 'url': f'{ctx.author.avatar_url}', 'icon_url': f'{ctx.author.avatar_url}'}
        
        lst = []

        for e in info['entries']:
            #lst.append(f'`{info["entries"].index(e) + 1}.` {e.get("title")} **[{YTDLSource.parse_duration(int(e.get("duration")))}]**\n')
            VId = e.get('id')
            VUrl = 'https://www.youtube.com/watch?v=%s' % (VId)
            lst.append(f'`{info["entries"].index(e) + 1}.` [{e.get("title")}]({VUrl})\n')

        lst.append('\n**Digite um numero para fazer sua escolha, Digite  ''cancel'' ''to exit**')
        cls.search["description"] = "\n".join(lst)

        em = discord.Embed.from_dict(cls.search)
        await ctx.send(embed=em, delete_after=45.0)

        def check(msg):
            return msg.content.isdigit() == True and msg.channel == channel or msg.content == 'cancel' or msg.content == 'Cancel'
        
        try:
            m = await bot.wait_for('message', check=check, timeout=45.0)

        except asyncio.TimeoutError:
            rtrn = 'timeout'

        else:
            if m.content.isdigit() == True:
                sel = int(m.content)
                if 0 < sel <= 10:
                    for key, value in info.items():
                        if key == 'entries':
                            """data = value[sel - 1]"""
                            VId = value[sel - 1]['id']
                            VUrl = 'https://www.youtube.com/watch?v=%s' % (VId)
                            partial = functools.partial(cls.ytdl.extract_info, VUrl, download=False)
                            data = await loop.run_in_executor(None, partial)
                    rtrn = cls(ctx, discord.FFmpegPCMAudio(data['url'], **cls.FFMPEG_OPTIONS), data=data)
                else:
                    rtrn = 'sel_invalid'
            elif m.content == 'cancel':
                rtrn = 'cancel'
            else:
                rtrn = 'sel_invalid'
        
        return rtrn

    @staticmethod
    def parse_duration(duration: int):
        if duration > 0:
            minutes, seconds = divmod(duration, 60)
            hours, minutes = divmod(minutes, 60)
            days, hours = divmod(hours, 24)

            duration = []
            if days > 0:
                duration.append('{}'.format(days))
            if hours > 0:
                duration.append('{}'.format(hours))
            if minutes > 0:
                duration.append('{}'.format(minutes))
            if seconds > 0:
                duration.append('{}'.format(seconds))
            
            value = ':'.join(duration)
        
        elif duration == 0:
            value = "LIVE"
        
        return value


class Song:
    __slots__ = ('source', 'requester')

    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester
    
    def create_embed(self):
        embed = (discord.Embed(title='Tocando Agora', description='```css\n{0.source.title}\n```'.format(self), color=discord.Color.blurple())
                .add_field(name='Duração', value=self.source.duration)
                .add_field(name='Pedido por', value=self.requester.mention)
                .add_field(name='Canal', value='[{0.source.uploader}]({0.source.uploader_url})'.format(self))
                .add_field(name='URL', value='[Click]({0.source.url})'.format(self))
                .add_field(name='Convite', value='[Click]( https://pxlme.me/Fiamoncini)'.format(self))
                .add_field(name='Site', value='[Click]( https://pxlme.me/SiteF)'.format(self))

                .set_thumbnail(url=self.source.thumbnail)
                .set_author(name=self.requester.name, icon_url=self.requester.avatar_url))
        return embed


class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]


class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()
        self.exists = True

        self._loop = False
        self._volume = 0.5
        self.skip_votes = set()

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()
            self.now = None

            if self.loop == False:
                # Try to get the next song within 3 minutes.
                # If no song will be added to the queue in time,
                # the player will disconnect due to performance
                # reasons.
                try:
                    async with timeout(180):  # 3 minutes
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    self.exists = False
                    return
                
                self.current.source.volume = self._volume
                self.voice.play(self.current.source, after=self.play_next_song)
                await self.current.source.channel.send(embed=self.current.create_embed())
            
            #If the song is looped
            elif self.loop == True:
                self.now = discord.FFmpegPCMAudio(self.current.source.stream_url, **YTDLSource.FFMPEG_OPTIONS)
                self.voice.play(self.now, after=self.play_next_song)
            
            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        self.skip_votes.clear()

        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state or not state.exists:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage('Esse comando não pode ser utilizado em canais privados!')

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send('Um erro ocorreu: {}'.format(str(error)))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != bot.user.id:
            print(f"{message.guild}/{message.channel}/{message.author.name}>{message.content}")
            if message.embeds:
                print(message.embeds[0].to_dict())

    @commands.command(name='join', invoke_without_subcommand=True)
    async def _join(self, ctx: commands.Context):
        """Entra na call em que você está."""

        destination = ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='sumonar')
    @commands.has_permissions(manage_guild=True)
    async def _summon(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None):
        """Sumona o bot no canal de voz.
         Se nenhum canal especificado, ele entra no qual você está.
        """

        if not channel and not ctx.author.voice:
            raise VoiceError('Você não está conectado a um canal de voz, e não escolheu para onde devo ir portanto não sei onde entrar.')

        destination = channel or ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()
        await ctx.message.add_reaction('✅')

    @commands.command(name='sair', aliases=['disconnect'])
    @commands.has_permissions(manage_guild=True)
    async def _leave(self, ctx: commands.Context):
        """Limpa a fila e sai da call."""

        if not ctx.voice_state.voice:
            return await ctx.send('Não estou conectado a nenhum canal de voz.')

        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]

    @commands.command(name='volume')
    @commands.is_owner()
    async def _volume(self, ctx: commands.Context, *, volume: int):
        """Define o volume do bot, de 0 a 100."""

        if not ctx.voice_state.is_playing:
            return await ctx.send('Não há nada tocando no momento.')

        if 0 > volume > 100:
            return await ctx.send('O volume tem de ser de 0 a 100%')

        ctx.voice_state.volume = volume / 100
        await ctx.send('Volume alterado para {}%'.format(volume))

    @commands.command(name='now', aliases=['current', 'playing'])
    async def _now(self, ctx: commands.Context):
        """Mostra a música tocando no momento."""
        embed = ctx.voice_state.current.create_embed()
        await ctx.send(embed=embed)

    @commands.command(name='pause', aliases=['pa'])
    @commands.has_permissions(manage_guild=True)
    async def _pause(self, ctx: commands.Context):
        """Pausa a música tocando no momento.."""
        print(">>>Pause Command:")
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='resume', aliases=['re', 'res'])
    @commands.has_permissions(manage_guild=True)
    async def _resume(self, ctx: commands.Context):
        """Resume a música se estiver parada."""

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='stop')
    @commands.has_permissions(manage_guild=True)
    async def _stop(self, ctx: commands.Context):
        """Para de tocar a música e limpa a fila."""

        ctx.voice_state.songs.clear()

        if ctx.voice_state.is_playing:
            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction('⏹')

    @commands.command(name='skip', aliases=['s'])
    async def _skip(self, ctx: commands.Context):
        """Pula a música e pula para a próxima da fila
        Caso você não tenha cargo suficiente será necessário uma votação de 3 pessoas para skippar.
        """

        if not ctx.voice_state.is_playing:
            return await ctx.send('Não tem nenhuma música tocando no momento.')

        voter = ctx.message.author
        if voter == ctx.voice_state.current.requester:
            await ctx.message.add_reaction('⏭')
            ctx.voice_state.skip()

        elif voter.id not in ctx.voice_state.skip_votes:
            ctx.voice_state.skip_votes.add(voter.id)
            total_votes = len(ctx.voice_state.skip_votes)

            if total_votes >= 1:
                await ctx.message.add_reaction('⏭')
                ctx.voice_state.skip()
            else:
                await ctx.send('Voto de skippar contado. **{}/3**'.format(total_votes))

        else:
            await ctx.send('Você já votou para pular essa música..')

    @commands.command(name='fila', aliases=['q'])
    async def _queue(self, ctx: commands.Context, *, page: int = 1):
        """Mosta a fila de músicas a serem tocadas..
        Caso você tenha mais de 10 músicas a fila, será adicionada uma página que você poderá ver.
        """

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Fila vazia.')

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(i + 1, song)

        embed = (discord.Embed(description='**{} Músicas:**\n\n{}'.format(len(ctx.voice_state.songs), queue))
                 .set_footer(text='Página {}/{}'.format(page, pages)))
        await ctx.send(embed=embed)

    @commands.command(name='misturar')
    async def _shuffle(self, ctx: commands.Context):
        """Mistura aleatóriamente a fila de músicas."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Fila vazia.')

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction('✅')

    @commands.command(name='remove')
    async def _remove(self, ctx: commands.Context, index: int):
        """Remove a música mais recente adicionada a fila"""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Fila sem nenhuma musica para retirar.')

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(name='loop')
    async def _loop(self, ctx: commands.Context):
        """Dá loop na música tocando no momento.
        Dê .loop novamente para sair do loop.
        """

        if not ctx.voice_state.is_playing:
            return await ctx.send('Nenhuma música tocando no momento.')

        # Inverse boolean value to loop and unloop.
        ctx.voice_state.loop = not ctx.voice_state.loop

        await ctx.message.add_reaction('✅')

    @commands.command(name='play', aliases=['p'])
    async def _play(self, ctx: commands.Context, *, search: str):
        """Toca uma música a sua escolha.
        Se já estiver uma música tocando, a música vai ser adicionada a fila.
        Se nenhuma URL for dada e a música não for encontrada no youtube o bot irá pesquisar em diversos outros sites.
        A lista dos sites que serão pesquisados está aqui: https://rg3.github.io/youtube-dl/supportedsites.html
        """

        async with ctx.typing():
            try:
                source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                await ctx.send('Aconteceu um erro a processar o pedido: {}'.format(str(e)))
            else:
                if not ctx.voice_state.voice:
                    await ctx.invoke(self._join)

                song = Song(source)
                await ctx.voice_state.songs.put(song)
                await ctx.send('Adicionado {}'.format(str(source)))
                embed = await ctx.message.add_reaction('✅')

    @commands.command(name='search')
    async def _search(self, ctx: commands.Context, *, search: str):
        """Pesquisa a música no youtube.
        Ele mostra os 10 primeiros resultados do Youtube. E a música pode ser escolhida digitando um número de 1 a 10 no chat, de acordo com a pesquisa.
        Você também pode digitar /cancelar para cancelar a pesquisa
      
        """
        async with ctx.typing():
            try:
                source = await YTDLSource.search_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                await ctx.send('Ocorreu um erro inesperado ao buscar: {}'.format(str(e)))
            else:
                if source == 'sel_invalid':
                    await ctx.send('Seleção Invalida')
                elif source == 'cancel':
                    await ctx.send(':white_check_mark:')
                elif source == 'timeout':
                    await ctx.send(':alarm_clock: **Tempo Acabou**')
                else:
                    if not ctx.voice_state.voice:
                        await ctx.invoke(self._join)

                    song = Song(source)
                    await ctx.voice_state.songs.put(song)
                    await ctx.send('Adicionado {}'.format(str(source)))
            
    @_join.before_invoke
    @_play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('Você não está conectado a nenhum canal de voz')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('O bot já está em um canal de voz.')


bot = commands.Bot(command_prefix='!', case_insensitive=True, description="Fiamoncini", help_command=None)
bot.add_cog(Music(bot))

@bot.event
async def on_ready():
    print('Logged in as:\n{0.user.name}\n{0.user.id}'.format(bot))
    print('BOT ON KRL')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name ="!help"))

@bot.command(name='say')
async def say(ctx, *, message):
  if ctx.author.id == 422108442103250955:
    await ctx.message.delete()
    await ctx.send(f"{message}".format(message))
  else:
      await ctx.send('VocÃª nÃ£o Ã© o desenvolvedor!')
      print ('Usaram .say e nÃ£o conseguiram')

@bot.command(name='dm')
async def DM(ctx, user: discord.User, *, message=None):
  if ctx.author.id == 422108442103250955:
    message = message or "teste"
    await user.send(message)
    await ctx.message.delete()
  else:
    await ctx.send('VocÃª nÃ£o Ã© o dono do bot para usar este comando')
    print ('Usaram .dm')

@bot.command(name='pedro')
async def pedro(ctx):
  await ctx.send('https://media.giphy.com/media/qHyURqMBj5WcKMehoy/giphy.gif')


@bot.command(aliases= ['limpar','deletar'], help= 'apagar')
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount= 5): # Set default value as None
    if amount == None:
        await ctx.channel.purge(limit=1000000)
    else:
        try:
            int(amount)
        except: # Error handler
            await ctx.send('Por favor digite uma quantia válida.')
        else:
            await ctx.channel.purge(limit=amount)


@bot.command(name='desligar', aliases=['bpara'])
@commands.is_owner()
async def botstop(ctx):
    print('Goodbye')
    await ctx.send('Tchau')
    await bot.logout()
    return


bot.run('ODg4ODI5MTE5NzcxNTkwNjk3.YUYYnw.LUcYJ2ojsl9SfkAjF_Qy66dicHM')