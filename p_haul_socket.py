import socket
import threading
import select

ph_service_port = 18862

# Keeps accepted sockets with addr:port key
# The sk.peer_name() reports the peer's key
# The get_by_name()
#
# Synchronization note -- docs say, that dicts
# are thread-safe in terms of add/del/read won't
# corrupt the dictionary. Assuming I undersand
# this correctly, there's no any locks around
# this one. The socket connection process would
# look like this:
#
#  clnt                         srv
#                               start_listener()
#  sk = create(srv)
#  srv.pick_up(sk.name()) - - > sk = get_by_name(name)
#
#  < at this point clnt.sk and src.sk are connected >
#
ph_sockets = {}

class ph_lsocket:
	def __init__(self, sock):
		self._sk = sock

	def fileno(self):
		return self._sk.fileno()

	def proceed(self, poll_list):
		clnt, addr = self._sk.accept()
		sk = ph_socket(clnt, addr)
		ph_sockets[addr] = sk
		poll_list.append(sk)
		print "Accepted connection from", addr

class ph_socket:
	def __init__(self, sock, hashv = None):
		self._sk = sock
		self._hashv = hashv

	def name(self):
		return self._sk.getsockname()

	def fileno(self):
		return self._sk.fileno()

	def criu_fileno(self):
		return self._criu_fileno

	def set_criu_fileno(self, val):
		self._criu_fileno = val

	def picked(self):
		self._hashv = None

	def proceed(self, poll_list):
		print "Dropping socket from poll list", self.name()
		poll_list.remove(self)
		if self._hashv:
			#
			# If client died before calling the get_by_name
			# the socket is still in ph_sockets dict, so we
			# need to drop one from it too
			#
			print " `- and from hash too"
			ph_sockets.pop(self._hashv, None)
			self._hashv = None

class ph_socket_listener(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		lsk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		lsk.bind(("0.0.0.0", ph_service_port))
		lsk.listen(4)
		self._sockets = [ph_lsocket(lsk)]

	def run(self):
		while True:
			r, w, x = select.select(self._sockets, [], [])
			for sk in r:
				sk.proceed(self._sockets)

def start_listener():
	lt = ph_socket_listener()
	lt.start()
	print "Listener started"

def create(tgt_host):
	csk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	csk.connect((tgt_host, ph_service_port))

	sk = ph_socket(csk)

	print "Connected ph socket to %s" % tgt_host
	return sk

def get_by_name(name):
	sk = ph_sockets.pop(name, None)
	if sk:
		print "Picking up socket", name
		sk.picked()

	return sk
