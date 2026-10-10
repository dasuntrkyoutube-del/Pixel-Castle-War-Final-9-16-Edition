import os,sys,random,math,time,queue,threading
from collections import defaultdict,deque
import pygame

BASE=os.path.dirname(os.path.abspath(__file__))
W,H=1280,720
FPS=60
RED=(239,81,96); BLUE=(75,166,251); GOLD=(255,214,109)
pygame.init()
pygame.display.set_caption('PIXEL CASTLE WAR - LIVE VERTICAL 9:16')
screen=pygame.display.set_mode((W,H),pygame.RESIZABLE)
canvas=pygame.Surface((W,H))
clock=pygame.time.Clock()
fontcache={}
def font(sz,bold=False):
 key=(sz,bold)
 if key not in fontcache: fontcache[key]=pygame.font.SysFont('consolas',sz,bold=bold)
 return fontcache[key]
def label(s,x,y,size=20,color=(245,246,255),center=False,bold=False):
 img=font(size,bold).render(str(s),True,color)
 canvas.blit(img,img.get_rect(center=(x,y)) if center else (x,y))
def rect(x,y,w,h,c,r=0): pygame.draw.rect(canvas,c,(int(x),int(y),int(w),int(h)),border_radius=r)
def outline(x,y,w,h,c,width=2,r=0): pygame.draw.rect(canvas,c,(int(x),int(y),int(w),int(h)),width,border_radius=r)

NAMES={'fire':'Fire Wizard','lightning':'Lightning Mage','arcane':'Wanderer Magican'}
ACTIONS=['Idle','Walk','Run','Attack_1','Attack_2','Hurt','Dead']
sheets={}
for typ,folder in NAMES.items():
 for action in ACTIONS:
  path=os.path.join(BASE,'assets',folder,action+'.png')
  if os.path.exists(path):
   sheet=pygame.image.load(path).convert_alpha()
   sheets[(typ,action)]=[sheet.subsurface((i*128,0,128,128)).copy() for i in range(sheet.get_width()//128)]

class Fighter:
 def __init__(self,team,name,typ=None):
  self.team=team;self.name=name[:14];self.typ=typ or random.choice(list(NAMES))
  self.x=355 if team=='red' else 925;self.y=random.choice([478,508,534]);self.hp=100;self.maxhp=100
  self.attack_cd=random.random();self.action='Walk';self.anim=0.;self.action_timer=0;self.wobble=random.random()*7;self.npc=(name=='NPC')
 def update(self,dt,game):
  self.attack_cd-=dt;self.anim+=dt*10
  if self.hp<=0:
   self.action='Dead';self.action_timer+=dt;return
  opponents=[e for e in game.units if e.team!=self.team and e.hp>0]
  near=min(opponents,key=lambda e:abs(self.x-e.x),default=None)
  direction=1 if self.team=='red' else -1
  if near and abs(near.x-self.x)<86:
   if self.attack_cd<=0:
    self.action='Attack_1';self.anim=0;self.action_timer=.4;self.attack_cd=(2.3 if self.npc else 1.0)+random.random()*.7
    near.hp-=random.randint(4,9) if self.npc else random.randint(11,23)
    game.particles.append(Particle(near.x,near.y-45,RED if self.team=='red' else BLUE))
    game.hits[self.team]+=1
    if random.random()<.24:play('hit')
  elif (self.team=='red' and self.x<880) or (self.team=='blue' and self.x>400):
   self.x+=direction*dt*(19 if self.npc else (40 if self.typ=='arcane' else 32))
   if self.action_timer<=0: self.action='Walk'
  elif self.attack_cd<=0:
   game.damage('blue' if self.team=='red' else 'red',(2 if self.npc else random.randint(4,9)))
   self.attack_cd=3.4 if self.npc else 1.35;self.action='Attack_2';self.action_timer=.5;self.anim=0
  self.action_timer=max(0,self.action_timer-dt)
 def draw(self):
  if self.hp<=0 and self.action_timer>1.2: return
  anim=sheets.get((self.typ,self.action),sheets.get((self.typ,'Idle')))
  if not anim:return
  idx=min(len(anim)-1,int(self.anim)%len(anim))
  if self.hp<=0: idx=min(len(anim)-1,int(self.action_timer*9))
  image=anim[idx]
  # Sprite authors face right; mirror blue side.
  if self.team=='blue':image=pygame.transform.flip(image,True,False)
  canvas.blit(image,(int(self.x)-64,int(self.y)-112))
  c=RED if self.team=='red' else BLUE
  rect(self.x-24,self.y-109,48,5,(39,37,53));rect(self.x-24,self.y-109,48*max(0,self.hp)/100,5,c)
  img=font(11,True).render(self.name,True,(249,249,255));canvas.blit(img,img.get_rect(center=(self.x,self.y-119)))

class Particle:
 def __init__(self,x,y,color):self.x=x;self.y=y;self.color=color;self.age=0
 def update(self,dt): self.age+=dt
 def draw(self):
  radius=max(1,int((1-self.age/.5)*24))
  if radius>0:pygame.draw.circle(canvas,self.color,(int(self.x),int(self.y)),radius,2)

class Game:
 def __init__(self):
  self.round=0;self.users={};self.scores=defaultdict(int);self.last_user_action={};self.latest=deque(maxlen=7)
  self.units=[];self.particles=[];self.hits=defaultdict(int);self.hp={};self.maxhp=1100
  self.totalwins={'red':0,'blue':0};self.phase='join';self.timer=0;self.winner=None
  self.queue=queue.Queue();self.youtube=None;self.mode='IDLE NPC';self.demo=False;self.demo_timer=0
  self.last_viewer=time.monotonic();self.npc_timer=4;self.idle_enabled=True
  self.reset()
 def reset(self):
  self.round+=1;self.hp={'red':self.maxhp,'blue':self.maxhp};self.units=[];self.particles=[]
  self.phase='battle';self.timer=150;self.winner=None;self.last_user_action.clear();self.hits=defaultdict(int)
  self.latest.appendleft(('SYSTEM',f'ROUND {self.round} STARTED','system'));self.npc_timer=5
 def damage(self,team,amount):
  if self.phase=='battle':self.hp[team]=max(0,self.hp[team]-amount)
 def comment(self,user,cmd):
  if not isinstance(cmd,str):return
  parts=cmd.lower().strip().split();cmd=parts[0] if parts else ''
  if cmd not in ('!red','!blue','!attack','!defend','!heal','!fire','!lightning','!magic','!spawn','!bomb','!help'):return
  now=time.monotonic(); key=user.lower()
  if user not in ('NPC','SYSTEM'):
   self.last_viewer=now
  if cmd in ('!red','!blue'):
   team=cmd[1:];self.users[key]=(user[:18],team);self.latest.appendleft((user,f'joined {team.upper()} team',team));return
  if cmd=='!help':return
  if self.phase!='battle':return
  if key not in self.users:
   self.latest.appendleft((user,'join first: !red or !blue','system'));return
  if now-self.last_user_action.get(key,-999)<1.2:return
  self.last_user_action[key]=now
  display,team=self.users[key];enemy='blue' if team=='red' else 'red'
  if cmd in ('!spawn','!fire','!lightning','!magic'):
   typ={'!fire':'fire','!lightning':'lightning','!magic':'arcane'}.get(cmd)
   count=sum(u.team==team and u.hp>0 for u in self.units)
   if count<16:self.units.append(Fighter(team,display,typ));self.scores[key]+=3
  elif cmd=='!attack':
   self.damage(enemy,random.randint(12,22));self.scores[key]+=2
   self.hits[team]+=1
  elif cmd in ('!defend','!heal'):
   self.hp[team]=min(self.maxhp,self.hp[team]+random.randint(12,23));self.scores[key]+=2
  elif cmd=='!bomb':
   # More powerful, with a 12-second per-viewer cooldown.
   bombkey=('bomb',key)
   if now-self.last_user_action.get(bombkey,-999)<12:return
   self.last_user_action[bombkey]=now
   self.damage(enemy,random.randint(33,55));self.scores[key]+=5
   self.hits[team]+=1
  self.latest.appendleft((display,cmd,team))
 def start_youtube(self,video_id):
  if not video_id:return
  try:import pytchat
  except ImportError:
   self.latest.appendleft(('SYSTEM','Install pytchat to connect YouTube','system'));return
  if self.youtube:self.youtube['running']=False
  state={'running':True};self.youtube=state;self.demo=False;self.mode='YOUTUBE LIVE';self.last_viewer=time.monotonic()
  def poll():
   try:
    chat=pytchat.create(video_id=video_id)
    while state['running'] and chat.is_alive():
     for item in chat.get().sync():self.queue.put((item.author.name,item.message))
     time.sleep(.2)
    chat.terminate()
   except Exception as ex:self.queue.put(('SYSTEM','Live chat error: '+str(ex)[:70]))
  threading.Thread(target=poll,daemon=True).start()
 def update(self,dt):
  while not self.queue.empty():
   name,msg=self.queue.get_nowait()
   if name=='SYSTEM':self.latest.appendleft((name,msg,'system'))
   else:self.comment(name,msg)
  if self.demo:
   self.demo_timer-=dt
   if self.demo_timer<=0:
    self.demo_timer=random.uniform(.35,.8)
    person=random.choice(['PixelHero','Sakura','Shadow','Dragon','Gamer07','Moon','Frost','Ruby','Knight99','Nova','FireLord','BlueWolf'])
    if person.lower() not in self.users:self.comment(person,random.choice(['!red','!blue']))
    else:self.comment(person,random.choices(['!attack','!spawn','!fire','!lightning','!magic','!defend','!bomb'],[30,25,12,10,10,10,3])[0])
  # Background activity only if nobody has issued commands recently.
  # NPCs are real in-game units, never masquerading as viewers or chat users.
  if self.phase=='battle' and self.idle_enabled and not self.demo and time.monotonic()-self.last_viewer>28:
   self.npc_timer-=dt
   if self.npc_timer<=0:
    self.npc_timer=random.uniform(17,25)
    living=[u for u in self.units if u.hp>0]
    npc_living=[u for u in living if u.npc]
    if len(living)<3 and len(npc_living)<2:
     eligible=[t for t in ('red','blue') if not any(u.team==t and u.hp>0 for u in npc_living)]
     if eligible:
      team=random.choice(eligible)
      self.units.append(Fighter(team,'NPC',random.choice(list(NAMES))))
  if self.phase=='battle':
   self.timer-=dt
   for unit in list(self.units):unit.update(dt,self)
   self.units=[u for u in self.units if u.hp>0 or u.action_timer<1.2]
   for team in ('red','blue'):
    if self.hp[team]<=0:
     self.winner='blue' if team=='red' else 'red';self.phase='ended';self.timer=9;self.totalwins[self.winner]+=1;break
   if self.phase=='battle' and self.timer<=0:
    self.winner='red' if self.hp['red']>=self.hp['blue'] else 'blue';self.totalwins[self.winner]+=1;self.phase='ended';self.timer=9
  else:
   self.timer-=dt
   if self.timer<=0:self.reset()
  for p in self.particles:p.update(dt)
  self.particles=[p for p in self.particles if p.age<.5]

def draw_castle(x,color,hp,maxhp,mirror=False):
 dark=(44,49,76);stone=(112,126,155);light=(160,174,195)
 rect(x,342,154,203,dark);rect(x+8,352,138,193,stone)
 for row in range(7):
  yy=355+row*26
  for col in range(4):
   xx=x+10+col*34+(16 if row%2 else 0)
   if xx<x+143:pygame.draw.line(canvas,dark,(xx,yy),(xx,yy+24),2)
  pygame.draw.line(canvas,dark,(x+10,yy),(x+143,yy),2)
 rect(x+42,308,70,59,dark);rect(x+49,315,56,54,light)
 for off in [0,34,68,102,136]:rect(x+off,326,19,27,dark)
 rect(x+51,478,53,67,(49,37,52));pygame.draw.arc(canvas,GOLD,(x+51,456,53,52),0,math.pi,4)
 rect(x+73,257,5,70,(212,220,225))
 pygame.draw.polygon(canvas,color,[(x+78,260),(x+78+(-63 if mirror else 63),280),(x+78,298)])
 for dx in [18,109]:rect(x+dx,389,22,37,(49,58,80));rect(x+dx+6,396,8,18,GOLD)
 rect(x+13,560,128,12,(22,28,46),5);rect(x+13,560,128*hp/maxhp,12,color,5)

def draw_bg(t):
 canvas.fill((28,36,66))
 pygame.draw.circle(canvas,(247,191,120),(640,136),80)
 for i in range(6):
  x=i*270-85;y=200+int(math.sin(i*3)*35)
  pygame.draw.polygon(canvas,(55,69,100),[(x-170,420),(x+100,y),(x+370,420)])
 for i in range(5):
  x=i*360-100
  pygame.draw.polygon(canvas,(43,85,94),[(x-200,505),(x+160,290),(x+520,505)])
 rect(0,545,W,H-545,(65,99,78));rect(0,576,W,144,(49,75,64))
 for i in range(38):
  x=(i*107+41)%W;y=565+(i*37)%145
  rect(x,y,7,3,(94,136,94))


# PORTRAIT BROADCAST VIEW 720 x 1280. Gameplay drawn at native 1280x720,
# then composited into a portrait canvas; sprites are left pixel-sharp.
PW,PH=720,1280
portrait=pygame.Surface((PW,PH))
screen=pygame.display.set_mode((PW,PH),pygame.RESIZABLE)
S=(15,20,39);PANEL=(27,36,60);PALE=(229,236,251)
# Sounds sourced from user-provided Sounds.rar, converted only by copying WAV files.
AUDIO_MAP={'hit':'Punch.wav','cast':'Flame1.wav','boom':'Explosion.wav',
 'big_boom':'Explosion2.wav','fire':'Flame1.wav',
 'lightning':'Thunderbolt.wav','arcane':'Blaster laser.wav',
 'win':'Access granted.wav','gate':'Gate open.wav','death':'Dead1.wav'}
sfx={};audio_channels={}
try:
 if not pygame.mixer.get_init():pygame.mixer.init(frequency=44100,size=-16,channels=2,buffer=1024)
 for key,filename in AUDIO_MAP.items():
  snd=pygame.mixer.Sound(os.path.join(BASE,'assets','sound','custom',filename))
  snd.set_volume({'boom':.37,'big_boom':.46,'lightning':.36,'win':.5,'hit':.28,'cast':.22,'fire':.28,'arcane':.26,'death':.22}.get(key,.3))
  sfx[key]=snd
except (pygame.error,OSError) as ex:
 print('Audio unavailable:',ex)
 sfx={}
muted=False
last_sound={}
explosion_frames={}
for kind in (1,2,3):
 pics=[]
 for i in range(1,11):
  path=os.path.join(BASE,'assets','explosions',f'{kind}_{i:02d}.png')
  if os.path.isfile(path):
   img=pygame.image.load(path).convert_alpha()
   # Cap render texture dimensions while retaining genuine source artwork.
   if max(img.get_size())>270:
    k=270/max(img.get_size());img=pygame.transform.scale(img,(max(1,int(img.get_width()*k)),max(1,int(img.get_height()*k))))
   pics.append(img)
 explosion_frames[kind]=pics
blasts=[]
projectiles=[]  # Active shots; initialized before the game loop.
def play(sound):
 if muted or sound not in sfx:return
 now=time.monotonic()
 if now-last_sound.get(sound,0)<({'hit':.16,'cast':.25,'fire':.25,'lightning':.5,'arcane':.25,'death':.35}.get(sound,.1)):return
 last_sound[sound]=now
 sfx[sound].play()
def blast(x,y,kind=1):
 blasts.append([x,y,0.0,kind]);play('big_boom' if kind==3 else 'boom')
base_reset=Game.reset
def game_reset(self):
 base_reset(self)
 projectiles.clear()
 blasts.clear()
Game.reset=game_reset
base_comment=Game.comment
def game_comment(self,user,cmd):
 old=self.hits.copy();units=len(self.units)
 base_comment(self,user,cmd)
 parts=cmd.lower().strip().split() if isinstance(cmd,str) else []
 c=parts[0] if parts else ''
 if c in ('!bomb','!attack') and sum(self.hits.values())>sum(old.values()):
  team=self.users.get(user.lower(),(None,None))[1]
  if team in ('red','blue'):
   projectiles.append({'x':float(390 if team=='red' else 885),
    'end':1020 if team=='red' else 270,
    'y':392 if c=='!bomb' else 405,
    'kind':3 if c=='!bomb' else 1,'team':team})
 elif c in ('!fire','!magic','!lightning','!spawn') and len(self.units)>units:
  play({'!fire':'fire','!magic':'arcane','!lightning':'lightning','!spawn':'gate'}[c])
Game.comment=game_comment
base_update=Game.update
def game_update(self,dt):
 was=self.phase
 base_update(self,dt)
 if was=='battle' and self.phase=='ended':
  play('win');projectiles.clear()
 for shot in projectiles[:]:
  direction=1 if shot['team']=='red' else -1
  shot['x']+=direction*(720 if shot['kind']==3 else 940)*dt
  if (direction>0 and shot['x']>=shot['end']) or (direction<0 and shot['x']<=shot['end']):
   blast(shot['end'],shot['y'],shot['kind'])
   projectiles.remove(shot)
 for a in blasts:a[2]+=dt
 blasts[:]=[a for a in blasts if a[2]<.75]
Game.update=game_update

def txt(s,x,y,size=22,color=PALE,center=False,bold=False):
 image=font(size,bold).render(str(s),True,color)
 portrait.blit(image,image.get_rect(center=(x,y)) if center else (x,y))
def panel(x,y,w,h,color=PANEL,r=12):pygame.draw.rect(portrait,color,(x,y,w,h),border_radius=r)
def meter(x,y,w,h,amount,color):
 panel(x,y,w,h,(62,69,93),5)
 if amount>0:panel(x,y,max(1,int(w*max(0,min(1,amount)))),h,color,5)
def portrait_ui(game,now):
 portrait.fill(S)
 # Dark pixel horizon and stars background.
 for i in range(40):
  sx=(37+i*167)%PW;sy=(19+i*71)%300
  pygame.draw.rect(portrait,(38,49,78),(sx,sy,3,3))
 txt('PIXEL CASTLE WAR',PW//2,48,37,GOLD,True,True)
 txt('RED  vs  BLUE',PW//2,91,28,(242,244,255),True,True)
 panel(24,120,672,166)
 txt('COMMENT TO PLAY!',PW//2,146,31,GOLD,True,True)
 txt('1. JOIN A TEAM:  !red  or  !blue',PW//2,191,21,PALE,True,True)
 txt('2. COMMENT A COMMAND TO ATTACK!',PW//2,232,21,(171,226,255),True,True)
 # Always visible command box at top.
 panel(24,302,672,124,(29,47,68))
 txt('TYPE THESE IN LIVE CHAT',PW//2,325,22,GOLD,True,True)
 txt('!attack    !defend    !heal    !spawn',PW//2,362,22,PALE,True,True)
 txt('!fire    !lightning    !magic    !bomb',PW//2,394,22,PALE,True,True)
 txt(f'ROUND {game.round}     TIME: {max(0,math.ceil(game.timer))}s',PW//2,453,25,GOLD,True,True)
 txt('RED CASTLE',40,481,19,RED,bold=True)
 txt('BLUE CASTLE',539,481,19,BLUE,bold=True)
 meter(36,511,310,23,game.hp['red']/game.maxhp,RED)
 meter(375,511,310,23,game.hp['blue']/game.maxhp,BLUE)
 txt(f'{int(game.hp["red"])} HP',44,541,18,PALE)
 txt(f'{int(game.hp["blue"])} HP',565,541,18,PALE)
 # Background is an actual 1280x720 game stage, resized with nearest-neighbor pixel art scaling.
 y0=567
 # Camera crops unused sky and battlefield edges, making units visibly larger.
 battle=canvas.subsurface((90,155,1100,565))
 scaled=pygame.transform.scale(battle,(PW,439))
 portrait.blit(scaled,(0,y0))
 pygame.draw.rect(portrait,(77,92,124),(0,y0,PW,439),3)
 panel(24,1010,672,48,(31,46,67))
 txt('RED WINS: '+str(game.totalwins['red']),46,1022,20,RED,bold=True)
 txt('BLUE WINS: '+str(game.totalwins['blue']),453,1022,20,BLUE,bold=True)
 panel(24,1075,340,178)
 txt('LATEST CHAT',43,1086,20,GOLD,bold=True)
 for i,(name,action,team) in enumerate(list(game.latest)[:5]):
  col=RED if team=='red' else BLUE if team=='blue' else GOLD
  txt(str(name)[:11],43,1118+i*25,15,col,bold=True)
  txt(str(action)[:17],158,1118+i*25,15,PALE)
 panel(377,1075,319,178)
 txt('TOP PLAYERS',393,1086,20,GOLD,bold=True)
 for i,(who,score) in enumerate(sorted(game.scores.items(),key=lambda it:-it[1])[:5]):
  name,team=game.users.get(who,(who,'red'))
  txt(f'{i+1}. {name[:12]}',393,1118+i*25,16,RED if team=='red' else BLUE)
  txt(str(score),648,1118+i*25,16,GOLD)
 mode='DEMO TEST' if game.demo else game.mode
 txt(f'{mode}  |  F3 LIVE  F2 TEST  M SOUND',PW//2,1269,15,(168,185,209),True)
 if game.phase=='ended':
  panel(95,734,530,150,(19,24,44))
  pygame.draw.rect(portrait,GOLD,(95,734,530,150),4,border_radius=12)
  txt(f'{game.winner.upper()} TEAM WINS!',PW//2,777,39,RED if game.winner=='red' else BLUE,True,True)
  txt(f'NEXT ROUND IN {math.ceil(max(0,game.timer))}s',PW//2,837,23,GOLD,True)

def prompt_video():
 try:
  import tkinter as tk
  from tkinter import simpledialog
  root=tk.Tk();root.withdraw();value=simpledialog.askstring('YouTube Live','Enter YouTube live video ID or full YouTube link:');root.destroy()
  if value:
   from urllib.parse import urlparse,parse_qs
   if 'youtube.com' in value:
    parsed=urlparse(value);value=parse_qs(parsed.query).get('v',[parsed.path.rstrip('/').split('/')[-1]])[0]
   elif 'youtu.be' in value:value=urlparse(value).path.strip('/')
   game.start_youtube(value.strip())
 except Exception as e:game.latest.appendleft(('SYSTEM',str(e)[:50],'system'))

game=Game();running=True;fullscreen=False
# On GitHub runners there is no keyboard; start chat listener from a secret.
video_id=os.environ.get('YOUTUBE_VIDEO_ID','').strip()
if video_id:
 game.start_youtube(video_id)
else:
 print('INFO: YOUTUBE_VIDEO_ID was not set; running slow NPC idle mode',flush=True)

while running:
 dt=min(.055,clock.tick(FPS)/1000);now=pygame.time.get_ticks()/1000
 for event in pygame.event.get():
  if event.type==pygame.QUIT:running=False
  if event.type==pygame.KEYDOWN:
   if event.key==pygame.K_ESCAPE:running=False
   elif event.key==pygame.K_F11:
    fullscreen=not fullscreen;screen=pygame.display.set_mode((PW,PH),pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE)
   elif event.key==pygame.K_F2:game.demo=not game.demo;game.mode='DEMO TEST' if game.demo else 'IDLE NPC';game.last_viewer=time.monotonic()
   elif event.key==pygame.K_m:muted=not muted
   elif event.key==pygame.K_r:game.reset()
   elif event.key==pygame.K_F3:prompt_video()
   elif event.key==pygame.K_1:game.comment('LocalRed','!red')
   elif event.key==pygame.K_2:game.comment('LocalBlue','!blue')
   elif event.key==pygame.K_q:game.comment('LocalRed','!fire')
   elif event.key==pygame.K_p:game.comment('LocalBlue','!lightning')
   elif event.key==pygame.K_a:game.comment('LocalRed','!attack')
   elif event.key==pygame.K_l:game.comment('LocalBlue','!attack')
 game.update(dt)
 draw_bg(now)
 draw_castle(158,RED,game.hp['red'],game.maxhp)
 draw_castle(966,BLUE,game.hp['blue'],game.maxhp,True)
 for unit in sorted(game.units,key=lambda u:u.y):unit.draw()
 for particle in game.particles:particle.draw()
 # Show every attack travelling toward its target before impact.
 for shot in projectiles:
  px,py=int(shot['x']),int(shot['y'])
  col=GOLD if shot['kind']==3 else (RED if shot['team']=='red' else BLUE)
  pygame.draw.circle(canvas,col,(px,py),14 if shot['kind']==3 else 9)
  pygame.draw.circle(canvas,(255,249,220),(px-3,py-3),4)
  pygame.draw.line(canvas,col,(px-(25 if shot['team']=='red' else -25),py), (px,py),5)
 for x,y,age,kind in blasts:
  seq=explosion_frames.get(kind,[])
  if seq:
   idx=min(len(seq)-1,int(age/.07));img=seq[idx]
   canvas.blit(img,img.get_rect(center=(int(x),int(y))))
 portrait_ui(game,now)
 w,h=screen.get_size();scale=min(w/PW,h/PH);sw,sh=int(PW*scale),int(PH*scale)
 screen.fill((0,0,0));screen.blit(pygame.transform.scale(portrait,(sw,sh)),((w-sw)//2,(h-sh)//2))
 pygame.display.flip()
pygame.quit()
