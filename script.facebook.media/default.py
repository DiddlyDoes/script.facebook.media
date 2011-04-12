#Facebook Media For Boxee

import os,urllib,urllib2,time
import sys, traceback

import xbmc, xbmcaddon, xbmcgui #@UnresolvedImport

#import traceback
import facebook

from facebook import GraphAPIError, GraphWrapAuthError

__author__ = 'ruuk (Rick Phillips)'
__url__ = 'http://code.google.com/p/facebook-media/'
__date__ = '04-12-2011'
__version__ = '0.5.0'
__addon__ = xbmcaddon.Addon(id='script.facebook.media')
__language__ = __addon__.getLocalizedString

THEME = 'Default'

ACTION_MOVE_LEFT      = 1
ACTION_MOVE_RIGHT     = 2
ACTION_MOVE_UP        = 3
ACTION_MOVE_DOWN      = 4
ACTION_PAGE_UP        = 5
ACTION_PAGE_DOWN      = 6
ACTION_SELECT_ITEM    = 7
ACTION_HIGHLIGHT_ITEM = 8
ACTION_PARENT_DIR     = 9
ACTION_PREVIOUS_MENU  = 10
ACTION_SHOW_INFO      = 11
ACTION_PAUSE          = 12
ACTION_STOP           = 13
ACTION_NEXT_ITEM      = 14
ACTION_PREV_ITEM      = 15
ACTION_SHOW_GUI       = 18
ACTION_PLAYER_PLAY    = 79
ACTION_MOUSE_LEFT_CLICK = 100
ACTION_CONTEXT_MENU   = 117

import locale
loc = locale.getdefaultlocale()
print loc
ENCODING = loc[1] or 'utf-8'

def ENCODE(string):
	return string.encode(ENCODING,'replace')

def LOG(message):
	print 'FACEBOOK MEDIA: %s' % message
	
def ERROR(message):
	LOG(message)
	traceback.print_exc()
	return str(sys.exc_info()[1])
	
class FacebookUser:
	def __init__(self,uid):
		self.id = uid
		self.email = __addon__.getSetting('login_email_%s' % uid)
		self.password = __addon__.getSetting('login_pass_%s' % uid)
		self.token = __addon__.getSetting('token_%s' % uid)
		self.pic = __addon__.getSetting('profile_pic_%s' % uid)
		self.username = __addon__.getSetting('username_%s' % uid)
		
	def updateToken(self,token):
		self.token = token
		__addon__.setSetting('token_%s' % self.id,str(token))

class WindowState:
	def __init__(self):
		self.items = None
		self.listIndex = 0
		self.settings = {}
			
class FacebookSession:
	def __init__(self):
		self.window = None
		self.graph = None
		self.states = []
		self.current_state = None
		self.curr_state_settings = {}
		self.paging = []
		self.cancel_progress = False
		self.progressVisible = False
		self.lastItemNumber = 0
		self.CACHE_PATH = os.path.join(__addon__.getAddonInfo('profile'),'cache')
		if not os.path.exists(self.CACHE_PATH): os.makedirs(self.CACHE_PATH)
		self.newUserCache = None
		self.currentUser = None
		self.setFriend()
		
		self.imageURLCache = {}
		self.loadImageURLCache()
		
		self.stateSettings = (	'current_friend_name',
								'current_user_pic',
								'current_user_name',
								'last_item_name',
								'current_nav_path')
		self.start()
		
	def start(self):
		user = self.getCurrentUser()
		
		if not user:
			self.openAddUserWindow()
			return
		
		self.graph = self.newGraph(	user.email,
									user.password,
									user.id,
									user.token,
									self.newTokenCallback )
		
		print user.username
		#print user.email
		
		self.loadOptions()
		self.CATEGORIES()
		self.setCurrentState()
		
	def newGraph(self,email,password,uid=None,token=None,new_token_callback=None):
		graph = facebook.GraphWrap(token,new_token_callback=new_token_callback)
		graph.setAppData('150505371652086',scope='user_photos,friends_photos,user_photo_video_tags,friends_photo_video_tags,publish_stream')
		graph.setLogin(email,password,uid)
		return graph
		
	def newTokenCallback(self,token):
		self.token = token
		if self.currentUser: self.currentUser.updateToken(token)
		
	def loadOptions(self):
		items = []
		for user in self.getUsers():
			item = xbmcgui.ListItem()
			item.setLabel(user.username)
			item.setThumbnailImage(user.pic)
			item.setProperty('uid',user.id)
			items.append(item)
		options = [	('add_user','facebook-media-icon-adduser.png','Add User','data'),
					('remove_user','facebook-media-icon-removeuser.png','Remove User','data'),
					('reauth_user','facebook-media-icon-reauth-user.png','Re-Authorize Current User','data')]
		for action,icon,label,data in options:
			item = xbmcgui.ListItem()
			item.setThumbnailImage(icon)
			item.setLabel(label)
			item.setProperty('action',action)
			item.setProperty('data',data)
			items.append(item)
		
		self.window.getControl(120).addItems(items)
		
	def openAddUserWindow(self,email='',password=''):
		pass
			
	def saveState(self):
		state = self.createCurrentState()
		self.states.append(state)
		
	def getListItems(self,alist):
		items = []
		for x in range(0,alist.size()):
			items.append(alist.getListItem(x))
		return items
	
	def createCurrentState(self,items=None):
		ilist = self.window.getControl(120)
		state = WindowState()
		if not items:
			items = self.getListItems(ilist)
			state.listIndex = ilist.getSelectedItem()
		state.items = items
		for set in self.stateSettings: state.settings[set] = self.curr_state_settings.get(set)
		return state
	
	def setCurrentState(self,items=None):
		self.current_state = self.createCurrentState(items)
		
	def popState(self,clear=False):
		if not self.states: return False
		state = self.states.pop()
		if not clear: self.restoreState(state)
		return True
	
	def restoreState(self,state,onload=False):
		if not state:
			LOG('restoreState() - No State')
			return
		for set in self.stateSettings: self.curr_state_settings[set] = ''
		for set in self.stateSettings: self.curr_state_settings[set] = state.settings.get(set,'')
		ilist = self.window.getControl(120)
		self.fillList(state.items)
		ilist.selectItem(state.listIndex)
		self.current_state = state
			
	def reInitState(self,state=None):
		if not state: state = self.current_state
		self.restoreState(state)
		self.setPathDisplay()

	def getRealURL(self,url):
		if not url: return url
		for ct in range(1,4):
			try:
				req = urllib2.urlopen(url)
				break
			except:
				LOG('getRealURL(): ATTEMPT #%s FAILED' % ct)
		else:
			return url
		return req.geturl()
	
	def setListFocus(self,nextprev,conn_obj):
		ilist = self.window.getControl(120)
		if nextprev == 'prev':
			if conn_obj.next: self.jumpToListEnd(ilist,-1)
			else: self.jumpToListEnd(ilist)
		else:
			if conn_obj.previous: ilist.selectItem(1)
				
	def jumpToListEnd(self,ilist,offset=0):
		idx = len(self.getListItems(ilist)) - 1
		idx += offset
		if idx < 0: idx = 0
		ilist.selectItem(idx)
		
	def getPagingItem(self,nextprev,url,itype,current_url='',uid=''):
		item = xbmcgui.ListItem()
		item.setThumbnailImage('facebook-media-icon-%s.png' % nextprev)
		if nextprev == 'prev': caption = 'PREVIOUS %s' % itype.upper()
		else: caption = 'NEXT %s' % itype.upper()
		if itype == 'albums':
			item.setLabel(caption)
		else:
			item.setProperty('caption',caption)
			item.setProperty('hidetube','true')
		
		item.setProperty('category','paging')
		item.setProperty('uid',uid)
		item.setProperty('paging',ENCODE(url))
		item.setProperty('nextprev',nextprev)
		item.setProperty('mediatype',itype)
		item.setProperty('from_url',current_url)
		item.setProperty('previous',self.getSetting('last_item_name'))
		return item
		
	def fillList(self,items):
		#Fix for unpredictable Boxee wraplist behavior
		if len(items) < 6:
			newitems = []
			for y in items: newitems.append(y)
			mult = 6/len(items)
			if mult < 2: mult = 2
			for x in range(1,mult): #@UnusedVariable
				for y in items: newitems.append(y)
			self.window.getControl(120).addItems(newitems)
		else:
			self.window.getControl(120).addItems(items)
		
	def CATEGORIES(self,item=None):
		LOG("CATEGORIES - STARTED")
		window = self.window
		uid = 'me'
		friend_thumb = None
		if item:
			self.saveState()
			uid = item.getProperty('fid')
			friend_thumb = item.getProperty('friend_thumb')
		
		items = []
		cids = ('albums','videos','friends','photosofme','videosofme')
		if uid == 'me':
			cats = ('ALBUMS','VIDEOS','FRIENDS','PHOTOS OF ME','VIDEOS OF ME')
		else:
			cats = ('ALBUMS','VIDEOS','FRIENDS','PHOTOS OF USER','VIDEOS OF USER')
			
		for cat,cid in zip(cats,cids):
			item = xbmcgui.ListItem()
			#item.setContentType("")
			item.setLabel(cat)
			item.setProperty('category',cid)
			item.setProperty('uid',uid)
			item.setThumbnailImage('facebook-media-icon-%s.png' % cid)
			if friend_thumb: item.setProperty('friend_thumb',friend_thumb)
			else: item.setProperty('friend_thumb','facebook-media-icon-%s.png' % cid)
			item.setProperty('background','')
			item.setProperty('previous',self.getSetting('last_item_name'))
			items.append(item)
				
		self.fillList(items)
		window.setFocusId(120)
		self.setCurrentState(items)
		self.setSetting('last_item_name','CATEGORIES')
		LOG("CATEGORIES - STOPPED")

	def ALBUMS(self,item):
		LOG('ALBUMS - STARTED')
		uid = item.getProperty('uid')
		paging = item.getProperty('paging')
		nextprev = item.getProperty('nextprev')
		fromUrl = item.getProperty('from_url')
		
		if not paging: self.saveState()
		
		self.startProgress('GETTING ALBUMS...')
		
		items = []
		try:
			self.graph.withProgress(self.updateProgress,0.5,100,'QUERYING FACEBOOK')
			if paging:
				if fromUrl:
					self.paging.append(fromUrl)
				else:
					if self.paging: paging = self.paging.pop()
				albums = self.graph.urlRequest(paging)
			else:
				self.paging = []
				albums = self.graph.getObject(uid).connections.albums()
				
			print albums.next
			print albums.previous
			
			cids = []
			for a in albums:
				cid = a.cover_photo()
				if cid:
					cids.append(cid)
			cover_objects = {}
			if cids: cover_objects = self.graph.getObjects(cids)
			
			if albums.previous:
				item = self.getPagingItem('prev', albums.previous, 'albums',uid=uid)
				items.append(item)	
			
			total = len(albums) or 1
			ct = 0
			offset = 50
			modifier = 50.0 / total
			for a in albums:
				ct += 1
				cover = None
				acp = a.cover_photo()
				if acp: cover = cover_objects[acp]
				if cover:
					tn_url = cover.picture('')
					src_url = cover.source('')
					self.imageURLCache[a.id] = tn_url
				else:
					if a.id in self.imageURLCache:
						tn_url = self.imageURLCache[a.id]
					else:
						tn = "https://graph.facebook.com/"+a.id+"/picture?access_token=" + self.graph.access_token
						tn_url = self.getRealURL(tn)
						self.imageURLCache[a.id] = tn_url
					src_url = tn_url.replace('_a.','_n.')
					
				if not self.updateProgress(int(ct*modifier)+offset,100,'ALBUM %s OF %s' % (ct,total)):
					return

				#aname = a.get('name','').encode('ISO-8859-1','replace')
				aname = ENCODE(a.name(''))
				
				item = xbmcgui.ListItem()
				item.setLabel(aname)
				item.setThumbnailImage(ENCODE(tn_url))
				item.setProperty('image0',ENCODE(src_url))
				item.setProperty('album',ENCODE(a.id))
				item.setProperty('uid',uid)
				item.setProperty('category','photos')
				item.setProperty('previous',self.getSetting('last_item_name'))
				items.append(item)
				
			if albums.next:
				item = self.getPagingItem('next', albums.next, 'albums', paging,uid=uid)
				items.append(item)
				
			self.saveImageURLCache()
		finally:
			self.endProgress()
	
		if items:
			self.fillList(items)
			self.setListFocus(nextprev, albums)
			self.setCurrentState(items)
		else:
			self.noItems('Albums')
		
		LOG('ALBUMS - STOPPED')
			
	def FRIENDS(self,uid='me'):
		LOG('FRIENDS - STARTED')
		self.saveState()
		
		self.startProgress('GETTING FRIENDS...')
		self.graph.withProgress(self.updateProgress,0.5,100,'QUERYING FACEBOOK')
		
		items = []
		try:
			friends = self.graph.getObject(uid).connections.friends(fields="picture,name")
			srt = []
			show = {}
			for f in friends:
				name = f.name('')
				s = name.rsplit(' ',1)[-1] + name.rsplit(' ',1)[0]
				srt.append(s)
				show[s] = f
				srt.sort()
			total = len(srt) or 1
			ct=0
			offset = 50
			modifier = 50.0 / total
			for s in srt:
				fid = show[s].id
				tn_url = show[s].picture('').replace('_q.','_n.')
				ct+=1
				self.updateProgress(int(ct*modifier)+offset, 100, 'FRIEND %s of %s' % (ct,total))
				
				#if fid in self.imageURLCache:
				#	tn_url = self.imageURLCache[fid]
				#else:
				#	tn = "https://graph.facebook.com/"+fid+"/picture?type=large&access_token=" + self.graph.access_token
				#	tn_url = self.getRealURL(tn)
				#	self.imageURLCache[fid] = tn_url
				name = show[s].name('')
				item = xbmcgui.ListItem()
				item.setLabel(ENCODE(name))
				item.setThumbnailImage(ENCODE(tn_url))
				item.setProperty('friend_thumb',ENCODE(tn_url))
				item.setProperty('uid',uid)
				item.setProperty('fid',ENCODE(fid))
				item.setProperty('category','friend')
				item.setProperty('previous',self.getSetting('last_item_name'))
				items.append(item)
				
			self.saveImageURLCache()
			self.endProgress()
		except GraphAPIError,e:
			self.endProgress()
			if not '#604' in str(e): raise
			LOG("CAN'T ACCESS USER'S FRIENDS")
		except:
			self.endProgress()
			raise
			
		if items:
			self.fillList(items)
			self.setCurrentState(items)
		else:
			self.noItems('Friends')
			
		LOG("FRIENDS - STOPPED")
		
	def PHOTOS(self,item):
		LOG("PHOTOS - STARTED")
		aid = item.getProperty('album')
		uid = item.getProperty('uid')
		paging = item.getProperty('paging')
		nextprev = item.getProperty('nextprev')
		fromUrl = item.getProperty('from_url')
		if item.getProperty('category') == 'photosofme': aid = uid
				
		if not paging: self.saveState()
		
		self.startProgress('GETTING PHOTOS...')
		self.graph.withProgress(self.updateProgress,0.5,100,'QUERYING FACEBOOK')
		
		items = []
		try:
			if paging:
				if fromUrl:
					self.paging.append(fromUrl)
				else:
					if self.paging: paging = self.paging.pop()
				photos = self.graph.urlRequest(paging)
			else:
				self.paging = []
				photos = self.graph.getObject(aid).connections.photos()
			print photos.next
			print photos.previous
			tot = len(photos) or 1
						
			ct=0
			offset = 50
			modifier = 50.0/tot
			if photos.previous:
				item = self.getPagingItem('prev', photos.previous, 'photos',uid=uid)
				items.append(item)
				
			if uid == 'me': uid = self.currentUser.id
			
			for p in photos:
				tn = p.picture('') + '?fix=' + str(time.time()) #why does this work? I have no idea. Why did I try it. I have no idea :)
				#tn = re.sub('/hphotos-\w+-\w+/\w+\.\w+/','/hphotos-ak-snc1/hs255.snc1/',tn) # this seems to get better results then using the random server
				item = xbmcgui.ListItem()
				item.setLabel(ENCODE(self.removeCRLF(p.name(p.id))))
				source = ENCODE(p.source())
				caption = self.makeCaption(p, uid)
				item.setPath(source)
				item.setProperty('category','photovideo')
				item.setProperty('hidetube','true')
				item.setLabel('')
				item.setProperty('image0',source)
				item.setThumbnailImage(ENCODE(tn))
				item.setProperty('uid',uid)
				item.setProperty('id',ENCODE(p.id))
				item.setProperty('caption',caption)
				if p.hasProperty('comments'): item.setProperty('comments','true')
				if p.hasProperty('tags'): item.setProperty('tags','true')
				item.setProperty('data',p.toJSON())
				item.setProperty('previous',self.getSetting('last_item_name'))
				items.append(item)
				ct += 1
				self.updateProgress(int(ct*modifier)+offset,100,message='Loading photo %s of %s' % (ct,tot))
				
			if photos.next:
				item = self.getPagingItem('next', photos.next, 'photos', paging,uid=uid)
				items.append(item)
				
			self.endProgress()
		finally:
			self.endProgress()
		if items:
			self.fillList(items)
			self.setListFocus(nextprev, photos)
			self.setCurrentState(items)
		else:
			self.noItems('Photos',paging)
		LOG("PHOTOS - STOPPED")
	
	def VIDEOS(self,item):
		LOG("VIDEOS - STARTED")
		
		uploaded = False
		uid = item.getProperty('uid')
		paging = item.getProperty('paging')
		nextprev = item.getProperty('nextprev')
		fromUrl = item.getProperty('from_url')
		if item.getProperty('category') != 'videosofme': uploaded = True
		
		if not paging: self.saveState()
		
		self.startProgress('GETTING VIDEOS...')
		self.graph.withProgress(self.updateProgress,0.5,100,'QUERYING FACEBOOK')
		
		items = []
		try:
			if paging:
				if fromUrl:
					self.paging.append(fromUrl)
				else:
					if self.paging: paging = self.paging.pop()
				videos = self.graph.urlRequest(paging)
			else:
				self.paging = []
				if uploaded: videos = self.graph.getObject(uid).connections.videos__uploaded()
				else: videos = self.graph.getObject(uid).connections.videos()
			print videos.next
			print videos.previous	
			if videos.previous:
				item = self.getPagingItem('prev', videos.previous, 'videos',uid=uid)
				items.append(item)
			
			if uid == 'me': uid = self.currentUser.id
			
			total = len(videos) or 1
			ct=0
			offset = 50
			modifier = 50.0/total
			for v in videos:
				item = xbmcgui.ListItem()
				tn = v.picture('') + '?fix=' + str(time.time()) #why does this work? I have no idea. Why did I try it. I have no idea :)
				#tn = re.sub('/hphotos-\w+-\w+/\w+\.\w+/','/hphotos-ak-snc1/hs255.snc1/',tn)
				caption = self.makeCaption(v, uid)
				item.setPath(ENCODE(v.source('')))
				item.setProperty('uid',uid)
				item.setProperty('id',ENCODE(v.id))
				item.setProperty('category','photovideo')
				item.setProperty('hidetube','true')
				item.setThumbnailImage(ENCODE(tn))
				item.setProperty('image0',ENCODE(tn))
				item.setProperty('caption',caption)
				if v.hasProperty('comments'): item.setProperty('comments','true')
				if v.hasProperty('tags'): item.setProperty('tags','true')
				item.setProperty('data',v.toJSON())
				item.setProperty('previous',self.getSetting('last_item_name'))
				items.append(item)
				ct+=1
				self.updateProgress(int(ct*modifier)+offset,100, 'Loading video %s of %s' % (ct,total))
				
			if videos.next:
				item = self.getPagingItem('next', videos.next, 'videos', paging,uid=uid)
				items.append(item)

		finally:
			self.endProgress()
		if items:
			self.fillList(items)
			self.setListFocus(nextprev, videos)
			self.setCurrentState(items)
		else:
			self.noItems('Videos',paging)
			
		LOG("VIDEOS - STOPPED")
		
	def makeCaption(self,obj,uid):
		name = ''
		f_id = obj.from_({}).get('id','')
		if f_id != uid:
			print '%s  = %s' % (f_id,uid)
			name = obj.from_({}).get('name','') or ''
			if name: name = '[COLOR green]FROM: %s[/COLOR][CR]' % name
		title = obj.name('')
		if title: title = '[COLOR yellow]%s[/COLOR][CR]' % title
		caption = name + title + obj.description('')
		return ENCODE(urllib.unquote(caption))
		
	def noItems(self,itype='items',paging=None):
		if not paging: self.popState(clear=True)
		message = "No %s or not authorized." % itype
		if paging: message = 'End of %s reached.' % itype
		xbmcgui.Dialog().ok("None Available", message)
		
	def saveImageURLCache(self):
		out = ''
		for k in self.imageURLCache:
			out += '%s=%s\n' % (k,self.imageURLCache[k])
				
		cache_file = os.path.join(self.CACHE_PATH,'imagecache')

		f = open(cache_file,"w")
		f.write(out)
		f.close()
		
	def loadImageURLCache(self):
		cache_file = os.path.join(self.CACHE_PATH,'facebook-media','imagecache')
		if not os.path.exists(cache_file): return
		
		f = open(cache_file,"r")
		data = f.read()
		f.close()
		
		for line in data.splitlines():
			k,v = line.split('=',1)
			self.imageURLCache[k] = v
		
	def mediaNextPrev(self,np):
		LOG("PHOTOS - %s" % np.upper())
		item = self.window.getControl(120).getItem(0)
		url = item.getProperty(np)
		print "%s URL: %s" % (np.upper(),url)
		if url:
			if self.itemType(item) == 'image':
				self.PHOTOS(url, isPaging=True)
			else:
				self.VIDEOS(url, isPaging=True)
			if np == 'prev':
				list = self.window.getControl(120)
				idx = len(list.getItems()) - 1
				if idx < 0: idx = 0
				self.window.getControl(120).setFocusedItem(idx)

	def menuItemSelected(self,select=False):
		state_len = len(self.states)
		try:
			item = self.window.getFocusedItem(120)
			
			cat = item.getProperty('category')
			uid = item.getProperty('uid') or 'me'
			
			if cat == 'friend':
				name = item.getLabel()
				self.CATEGORIES(item)
				self.setFriend(name)
				self.setSetting('last_item_name',item.getLabel())
				self.setPathDisplay()
				return
			else:
				if uid == 'me': self.setFriend()
				
			if cat == 'albums':
				self.ALBUMS(item)
			elif cat == 'photos':
				self.PHOTOS(item)
			elif cat == 'friends':
				self.FRIENDS(uid)
			elif cat == 'videos':
				self.VIDEOS(item)
			elif cat == 'photosofme':
				self.PHOTOS(item)
			elif cat == 'videosofme':
				self.VIDEOS(item)
			elif cat == 'photovideo':
				if not select:
					if self.showPhotoMenu():
						return
				self.setCurrentState()
				self.setFriend('')
				self.preMediaSetup()
				self.showMedia(item)
			elif cat == 'paging':
				self.setSetting('last_item_name',item.getProperty('previous'))
				if item.getProperty('mediatype') == 'photos': 		self.PHOTOS(item)
				elif item.getProperty('mediatype') == 'videos': 	self.VIDEOS(item)
				elif item.getProperty('mediatype') == 'albums': 	self.ALBUMS(item)
				return
			
			self.setSetting('last_item_name',item.getLabel())
			self.setPathDisplay()
		except GraphWrapAuthError,e:
			if len(self.states) > state_len: self.popState()
			if e.type == 'RENEW_TOKEN_FAILURE':
				response = xbmcgui.Dialog().yesno("TOKEN ERROR", "Failed to renew authorization. Would you like to Re-Authorize?", "No", "Yes")
				if response:
					self.openAddUserWindow(self.currentUser.email, self.currentUser.password)
			else:
				message = ERROR('UNHANDLED ERROR')
				xbmcgui.Dialog().ok('ERROR',message)
		except:
			if len(self.states) > state_len: self.popState()
			message = ERROR('UNHANDLED ERROR')
			xbmcgui.Dialog().ok('ERROR',message)
		
	def menuItemDeSelected(self):
		if not self.popState():
			self.window.setFocusId(125)
	
	def optionMenuItemSelected(self):
		print "OPTION ITEM SELECTED"
		item = self.window.getFocusedItem(125)
		self.window.setFocusId(120)
		uid = item.getProperty('uid')
		if uid:
			self.setCurrentUser(uid)
		else:
			action = item.getProperty('action')
			if action == 'add_user':
				self.openAddUserWindow()
			elif action == 'remove_user':
				self.removeUserMenu()
			elif action == 'reauth_user':
				self.openAddUserWindow(self.currentUser.email, self.currentUser.password)
		
	def photovideoMenuSelected(self):
		self.window.setFocusId(120)
		item = self.window.getFocusedItem(128)
		name = item.getProperty('name')
		itemNumber = int(item.getProperty('item_number'))
		if name == 'slideshow':
			self.setFriend()
			items = self.window.getControl(120).getItems()
			self.preMediaSetup()
			self.showImages(items,itemNumber,options=(False,False,False))
		elif name == 'tags':
			self.openTagsWindow()
		elif name == 'comments':
			self.doCommentDialog(itemNumber)
		elif name == 'likes':
			self.doLike(itemNumber)
	
	def openTagsWindow(self):
		pass
	
	def doCommentDialog(self,itemNumber):
		comment = doKeyboard("Enter Comment",'',False)
		if not comment: return
		item = self.window.getControl(120).getItem(int(itemNumber))
		pv_obj = self.graph.fromJSON(item.getProperty('data'))
		pv_obj.comment(comment)
		self.updateMediaItem(item,pv_obj)
		
	def doLike(self,itemNumber):
		item = self.window.getControl(120).getItem(int(itemNumber))
		pv_obj = self.graph.fromJSON(item.getProperty('data'))
		pv_obj.like()
		self.updateMediaItem(item,pv_obj)
		
	def updateMediaItem(self,item,pv_obj=None):
		if not pv_obj: pv_obj = self.graph.fromJSON(item.getProperty('data'))
		item.setProperty('data',pv_obj.updateData().toJSON())
		if pv_obj.hasProperty('comments'): item.setProperty('comments','true')
		if pv_obj.hasProperty('tags'): item.setProperty('tags','true')
		#items = self.window.getControl(120).getItems()
		#idx=0
		#for i in items:
		#	if i.getProperty('id') == item.getProperty('id'):
		#		break
		#	idx+=1
		#else:
		#	return
		#items[idx] = item
		#self.window.getControl(120).setItems(items)
		
		
		
	def showPhotoMenu(self):
		self.setCurrentState()
		items = []
		itemNumber = self.window.getControl(120).getFocusedItem()
		item = self.window.getFocusedItem(120)
		pv_obj = self.graph.fromJSON(item.getProperty('data'))
		comments_string = ''
		tags_string = ''
		likes_string = ''
		comments = pv_obj.comments()
		if comments:
			for c in comments:
				name = c.from_({}).get('name','')
				comments_string += '[COLOR yellow]%s:[/COLOR][CR]%s[CR][CR]' % (name,c.message(''))
		tags = pv_obj.tags()
		if tags:
			for t in tags:
				tags_string += '[COLOR yellow]%s[/COLOR][CR]' % t.name('')
		likes = pv_obj.connections.likes()
		if likes:
			for l in likes:
				likes_string += '[COLOR yellow]%s[/COLOR][CR]' % l.name('')
		#if comments:
		items.append(self.createPhotoMenuItem('comments', 'COMMENTS','Click to add a comment', comments_string, itemNumber))
		if tags:
			items.append(self.createPhotoMenuItem('tags', 'TAGS', 'Click to view tagged image', tags_string, itemNumber))
		items.append(self.createPhotoMenuItem('likes', 'LIKES (%s)' % len(likes), 'Click to "like" this item', likes_string, itemNumber))
		if self.itemType(item) == 'image':
			items.append(self.createPhotoMenuItem('slideshow', 'SLIDESHOW', 'Click to view a slideshow', '', itemNumber))
			if tags: self.createTagsWindow(pv_obj)
		self.window.getControl(128).setItems(items)
		self.window.setFocusId(128)
		return True
	
	def createPhotoMenuItem(self,name,label,sublabel,data,itemNumber):
		item = xbmcgui.ListItem()
		item.setLabel(label)
		item.setProperty('sublabel',sublabel)
		item.setProperty('name',name)
		item.setProperty('item_number',str(itemNumber))
		item.setProperty('data',ENCODE(data))
		return item
		
		
	def removeUserMenu(self):
		uids = self.getUserList()
		options = []
		for uid in uids: options.append(self.getSetting('username_%s' % uid))

		idx = xbmcgui.Dialog().select('Choose User To Remove',options)
		if idx < 0:
			return
		else:
			uid = uids[idx]
			self.removeUser(uid)		
		
	def removeUser(self,uid):
		self.removeUserFromList(uid)
		self.clearSetting('login_email_%s' % uid)
		self.clearSetting('login_pass_%s' % uid)
		self.clearSetting('token_%s' % uid)
		self.clearSetting('profile_pic_%s' % uid)
		self.clearSetting('username_%s' % uid)
		self.setSetting('current_user','')
		self.currentUser = None
		self.getCurrentUser()
		self.loadOptions()
		
	def setPathDisplay(self):
		path = []
		for state in self.states:
			path.append(state.settings.get('last_item_name'))
		path.append(self.getSetting('last_item_name'))
		path = ' : '.join(path[1:])
		self.curr_state_settings['current_nav_path'] = path
		LOG('PATH - %s' % path)
		
	def setFriend(self,name=''):
		self.curr_state_settings['current_friend_name'] = name
		
	def startProgress(self,message):
		self.cancel_progress = False
		self.window.setFocusId(160)
		self.window.getLabel(152).setLabel(message)
		self.progressVisible = True
		
	def updateProgress(self,ct,total,message=''):
		if not self.progressVisible: return
		if self.cancel_progress: return False
		try:
			if ct < 0 or ct > total:
				LOG('PROGRESS OUT OF BOUNDS')
				return
			pct = int((ct / float(total)) * 20) * 5
			window = self.window
			self.setSetting('progress',str(pct))
			window.getLabel(152).setLabel(message)
		except:
			return False
		return True
	
	def endProgress(self):
		self.progressVisible = False
		self.window.setFocusId(120)
	
	def cancelProgress(self):
		LOG('PROGRESS CANCEL ATTEMPT')
		self.cancel_progress = True
		
	def preMediaSetup(self):
		blank = []
		blank.append(xbmcgui.ListItem())
		self.window.getControl(120).setItems(blank)
		
	def showImages(self,items,number=0,options=(True,False,True)):
		LOG('SHOW IMAGES')
		new_items = []
		for i in items:
			if not self.itemType(i) == 'other': new_items.append(i) 
		mc.getPlayer().PlaySlideshow(new_items, options[0], options[1], str(number), options[2])
		
	def showImage(self,item):
		items = []
		items.append(item)
		self.showImages(items)
		
	def showVideo(self,item):
		mc.getPlayer().Play(item)
		
	def showMedia(self,item):
		if self.itemType(item) == 'image':
			self.showImage(item)
		else:
			self.showVideo(item)
		
	def itemType(self,item):
		mtype = item.getMediaType()
		if mtype == mc.ListItem.MEDIA_PICTURE:
			return 'image'
		elif mtype == mc.ListItem.MEDIA_VIDEO_OTHER:
			return 'video'
		else:
			return 'other'
	
	def getFocusedItem(self,list_id):
		lc = self.window.getList(list_id)
		itemNumber = lc.getFocusedItem()
		self.lastItemNumber = itemNumber
		return lc.getItem(itemNumber)
	
	def removeCRLF(self,text):
		return " ".join(text.split())
		
	def makeAscii(self,name):
		return name.encode('ascii','replace')
	
	def getFile(self,url,target_file):
		try:
			request = urllib2.urlopen(url)
			target_file = self.fixExtension(request.info().get('content-type',''),target_file)
		except:
			print 'ERROR: urlopen() in getFile()'
			return ''
		f = open(target_file,"wb")
		f.write(request.read())
		f.close()
		return target_file
	
	def fixExtension(self,content_type,fn):
		if not 'image' in content_type: return
		ext = content_type.split('/',1)[-1]
		if not ext in 'jpeg,png,gif,bmp': return
		if ext == 'jpeg': ext = 'jpg'
		fn = os.path.splitext(fn)[0] + '.' + ext
		return fn
	
	def addUser(self,email=None,password=None):
		try:
			if self.newUserCache:
				self.addUserPart2()
				return
			LOG("ADD USER PART 1")
			self.setSetting('auth_step_1','pending')
			if not email:
				email = doKeyboard("Login Email")
			if not email:
				mc.CloseWindow()
				return
			if not password:
				password = doKeyboard("Login Password",hidden=True)
			if not password:
				mc.CloseWindow()
				return
			self.newUserCache = (email,password)
			self.setSetting('auth_step_1','complete')
			self.setSetting('auth_step_2','pending')
			self.getAuth(email,password)
		except:
			message = ERROR('ERROR')
			mc.HideDialogWait()
			xbmcgui.Dialog().ok('Authorization Error',message)
			mc.CloseWindow()
			self.newUserCache = None
		
	def addUserPart2(self):
		LOG("ADD USER PART 2")
		mc.ShowDialogWait()
		self.setSetting('auth_step_2','complete')
		self.setSetting('auth_step_3','pending')
		email,password = self.newUserCache
		self.newUserCache = None
		graph = self.newGraph(email, password)
		graph.getNewToken()
		self.setSetting('auth_step_3','complete')
		self.setSetting('auth_step_4','pending')
		user = graph.getObject('me',fields='id,name,picture')
		uid = user.id
		username = user.name()
		if not self.addUserToList(uid):
			LOG("USER ALREADY ADDED")
		self.setSetting('login_email_%s' % uid,email)
		self.setSetting('login_pass_%s' % uid,password)
		self.setSetting('username_%s' % uid,username)
		self.setSetting('token_%s' % uid,graph.access_token)
		#if self.token: self.setSetting('token_%s' % uid,self.token)
		self.setSetting('profile_pic_%s' % uid,user.picture('').replace('_q.','_n.'))
		#self.getProfilePic(uid,force=True)
		self.setSetting('auth_step_4','complete')
		mc.HideDialogWait()
		xbmcgui.Dialog().ok("User Added",ENCODE(username))
		mc.CloseWindow()
		self.loadOptions()
		if not self.getSetting('has_user'):
			self.setSetting('has_user','true')
			self.start()
		#self.setCurrentUser(uid)
		return uid
	
	def getUserList(self):
		ustring = self.getSetting('user_list')
		if not ustring: return []
		return ustring.split(',')
	
	def getUsers(self):
		ulist = []
		for uid in self.getUserList():
			ulist.append(FacebookUser(uid))
		return ulist
	
	def addUserToList(self,uid):
		ulist = self.getUserList()
		if uid in ulist: return False
		ulist.append(uid)
		self.setSetting('user_list',','.join(ulist))
		return True
	
	def removeUserFromList(self,uid):
		ulist = self.getUserList()
		if not uid in ulist: return
		new = []
		for u in ulist:
			if u != uid: new.append(u)
		self.setSetting('user_list',','.join(new))
		
	def setCurrentUser(self,uid):
		self.currentUser = FacebookUser(uid)
		self.setSetting('current_user', uid)
		u = self.currentUser
		self.setSetting('current_user_name', u.username)
		self.updateUserPic()
		if self.graph: self.graph.setLogin(u.email,u.password,u.id,u.token)
		
	def getCurrentUser(self):
		if self.currentUser: return self.currentUser
		uid = self.getSetting('current_user')
		if not uid:
			ulist = self.getUserList()
			if ulist:
				uid = ulist[0]
				if uid: self.setCurrentUser(uid)
		print uid
		if not uid: return None
		self.currentUser = FacebookUser(uid)
		self.setSetting('current_user_name', self.currentUser.username)
		self.updateUserPic()
		return self.currentUser
	
	def updateUserPic(self):
		self.setSetting('current_user_pic','')
		outfile = os.path.join(self.CACHE_PATH,'current_user_pic')
		self.setSetting('current_user_pic',self.getFile(self.currentUser.pic,outfile))
		
	def createTagsWindow(self,photo):
		width = int(photo.width(0))
		height = int(photo.height(0))
		if not width or not height: return
		tags = photo.tags()
		source = photo.source('')
		tagbox = '''
			<control type="image">
				<posx>%s</posx>
				<posy>%s</posy>
				<width>%s</width>
				<height>%s</height>
				<texture border="3">facebook-media-outline-box.png</texture>
				<visible>$INFO[StringCompare(Container(120).ListItem.Label2,%s)]</visible>
			</control>'''
			
		tagitem = '''
				<item>
					<label>%s</label>
					<label2>%s</label2>
					<onclick lang="python">
<![CDATA[
pass
]]>
					</onclick>
				</item>'''
		aspect = width/float(height)
		x=0
		y=0
		if aspect < (16/9.0):
			mod = (720.0/height)
			wmod = int(mod * width)
			hmod = 720
			x = (1280 - wmod)/2
			y = 0
		else:
			mod = (1280.0/width) 
			wmod = 1280
			hmod = int(mod * height)
			x = 0
			y = (720 - hmod) / 2
			
		box_len = 200
		box_off = box_len/2
		
		template_file_path = os.path.join(mc.getApp().getAppDir(),'tags.xml')
		tags_file_path = os.path.join(mc.getApp().getAppDir(),'skin','Boxee Skin NG','720p','tags.xml')
		
		tags_file = open(template_file_path,'r')
		xml = tags_file.read()
		tags_file.close()
		
		xml = xml.replace('G_X',str(x))
		xml = xml.replace('G_Y',str(y))
		xml = xml.replace('I_WIDTH',str(wmod))
		xml = xml.replace('I_HEIGHT',str(hmod))
		xml = xml.replace('TAGGED_IMAGE',source)
		
		boxes = ''
		items = ''
		for tag in tags:
			tag_name = tag.name('')
			tag_id = tag.id or tag_name
			tag_id = 'ID-' + tag_id.replace(' ','')
			tag_x = int(wmod * (float(tag.x(0))/100)) - box_off
			tag_y = int(hmod * (float(tag.y(0))/100)) - box_off
			boxes += tagbox % (tag_x,tag_y,box_len,box_len,tag_id)
			items += tagitem % (tag_name,tag_id) 
		
		xml = xml.replace('<!-- TAGBOXES -->',boxes)
		xml = xml.replace('<!-- TAGITEMS -->',items)
		
		tags_file = open(tags_file_path,'w')
		tags_file.write(xml)
		tags_file.close()
			
	def clearSetting(self,key):
		mc.getApp().getLocalConfig().Reset(str(key))
		
	def setSetting(self,key,value):
		mc.getApp().getLocalConfig().setValue(str(key),str(value))
		
	def getSetting(self,key):
		return mc.getApp().getLocalConfig().getValue(key)
	
	def getAuth(self,email='',password=''):
		redirect = urllib.quote('http://2ndmind.com/facebookphotos/complete.html')
		scope = urllib.quote('user_photos,friends_photos,user_photo_video_tags,friends_photo_video_tags,user_videos,friends_videos,publish_stream')
		url = urllib.quote('https://www.facebook.com/dialog/oauth?client_id=150505371652086&redirect_uri=%s&type=user_agent&scope=%s' % (redirect,scope))
		url = 'http://www.facebook.com/login.php?api_key=194599440576989&next=%s' % url
		launchBoxeeBrowser(url,email=email,password=password,debug='NONE')
		#token = fb.graph.extractTokenFromURL(url)
		#if fb.graph.tokenIsValid(token):
		#	fb.graph.saveToken(token)
		#	return token
		#return None

def launchBoxeeBrowser(url,**kwargs):
	from urllib import quote
	from urlparse import urlparse,urlunparse
	
	uri = urlparse(url)

	if not uri[0]:
		url = "http://"+urlunparse(uri)
		uri = urlparse(url)

	domain = uri[1]
	domain = domain.split('.')

	if len(domain) > 2:
		domain = domain[-2:]

	domain = ".".join(domain)

	args = ''
	for k in kwargs:
		args += '&%s=%s' % (k,quote(kwargs[k]))
		
	#path = 'flash://%s/src=%s%s&bx-jsactions=%s' % (domain, quote(url),args,quote('http://dir.boxee.tv/apps/browser/browser.js'))
	path = 'flash://%s/src=%s%s&bx-jsactions=%s' % (domain, quote(url),args,quote('http://2ndmind.com/boxee/facebook-media/fbauth.js'))
	
	item = xbmcgui.ListItem()
	item.setLabel("Authorize")
	item.setAddToHistory(False)
	item.setReportToServer(False)
	item.setContentType("application/x-shockwave-flash")
	item.setPath(path)
	player = mc.Player()
	player.Play(item)

def doKeyboard(prompt,default='',hidden=False):
	keyboard = xbmc.Keyboard(default,prompt)
	keyboard.setHiddenInput(hidden)
	keyboard.doModal()
	if not keyboard.isConfirmed(): return None
	return keyboard.getText()

BOXEE_VERSION = mc.getInfoString('System.BuildVersion')
LOG('Boxee Version: %s' % BOXEE_VERSION)

params = mc.Parameters()
params['none'] = 'NONE'

config = mc.getApp().getLocalConfig()
config.setValue('current_user_pic','facebook-media-icon-generic-user.png')
config.setValue('current_friend_name','')
config.setValue('progress','')
config.setValue('last_item_name','OPTIONS')
config.setValue('current_nav_path','')

CLOSEREADY = False
mc.getApp().ActivateWindow(14000,params)