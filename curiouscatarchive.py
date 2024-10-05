import requests
import json
import sys
import re
import os
import argparse
from datetime import datetime
from time import sleep

###Setvars
url = "https://curiouscat.live/kicksomeacid"

initialdir = os.getcwd()
downloadLocal = None

##ARGUMENT PARSEING###
parser = argparse.ArgumentParser(prog='ccarchiver', description='Create a local archive of CuriousCat accounts.')
parser.add_argument('-f', '--file', action='store_true', help='use a file containing a list of usernames on seperate lines instead')
parser.add_argument('-v', '--verbose', action='store_true', help='Display verbose Output')
parser.add_argument('-l', '--local', action='store_true', help='Automatically Download Local Copys')
parser.add_argument('-n', '--concurrentDownloads', type=int, default=5, help='Number of Accounts To Download At Once (Default: 5)')
parser.add_argument('Username', help='The Username of the account to archive, or file containing usernames')

args = vars(parser.parse_args())

if args['local'] == True:
	downloadLocal = True

if args['file'] == False:
	usernames = [args['Username']]
else:
	if not os.path.isfile(args['Username']):
		print('The file specified does not exist')
		sys.exit()
	f = open(args['Username'])
	usernames = f.read().splitlines()


#Main Function to downloadUserAnswers
def downloadUserAnswers(userdata):
	username = userdata[0]
	status = userdata[1]
	#Get The Main Content Of A User Profile
	querystring = {"username":username}
	response = requests.request("GET", url, params=querystring)
	fullJson = response.json()
	if 'error_code' in fullJson.keys():
		if fullJson['error_code'] == 'profile_does_not_exist':
			print("User '%s' could not be found, skipping." % username)
			status['_progress_counter'] += 1
			updateStatus(username, None, status)
		elif fullJson['error_code'] == 'ratelimited':
			print('ratelimited, waiting 60 seconds to retry...')
			sleep(60)
			downloadUserAnswers(username)
		return

	time = datetime.now()
	updateStatus(username, "Archiving %s at %s" % (username, time.strftime("%Y/%m/%d %H:%M:%S")), status)

	#Set Directory
	workingdir = os.path.join(initialdir, 'CCArchive%s' % username)
	if not os.path.exists(workingdir):
	   os.makedirs(workingdir)
	
	while not os.path.exists(workingdir):
		sleep(1)

	os.chdir(workingdir)

	#Get Post Archive
	answercount = fullJson['answers']
	while True and answercount > 0:
		try:
			if fullJson['posts'][-1]['type'] == "post":
				lastTimestamp = fullJson['posts'][-1]['post']['timestamp']
			elif fullJson['posts'][-1]['type'] == "status":
				lastTimestamp = fullJson['posts'][-1]['status']['timestamp']
			elif fullJson['posts'][-1]['type'] == "shared_post":
				lastTimestamp = fullJson['posts'][-1]['shared_timestamp']
			else:
				print(json.dumps(fullJson['posts'][-1]))
				raise
		except Exception as e:
			print(json.dumps(fullJson['posts'][-1]))
			raise e
		


		querystring = {"username":username,"max_timestamp":lastTimestamp-1}
		response = requests.request("GET", url, params=querystring)

		if response.json()['posts'] == []:
			break

		fullJson['posts'] = fullJson['posts'] + response.json()['posts']

		updateStatus(username, "Downloading Answers [%d/%d]" % (len(fullJson['posts']),answercount), status)
		pass

	
	#WriteToFile
	updateStatus(username, "Saving Raw Json to file: %sAnswers%s.json" % (username, time.strftime("%Y%m%d-%H%M%S")), status)
	out = open("%sAnswers%s.json" % (username, time.strftime("%Y%m%d-%H%M%S")), 'w')
	out.write(json.dumps(fullJson))

	#Check For Local Copy
	if downloadLocal == False:
		status['_progress_counter'] += 1
		updateStatus(username, None, status)
		return


	
	#Extracts Links From Raw JSON
	updateStatus(username, "Extracting Links From Json...", status)
	jsonraw = json.dumps(fullJson)

	regexQuery = '(https?://[^ ]*?\.curiouscat.qa/.+?)"'

	alllinks = re.findall(regexQuery, jsonraw)

	links = []

	for link in alllinks:
		if link not in links:
			links.append(link)


	#Download Local Copy of images
	media_directory = os.path.join(workingdir, 'Media')
	if not os.path.exists(media_directory):
	   os.makedirs(media_directory)


	for index, link in enumerate(links):
		linkpath = re.sub('(/|https?://[^ ]*?\.curiouscat.qa/)', '', link)
		response = requests.get(link)

		updateStatus(username, "Downloading Images [%d/%d]..." % (index + 1, len(links)), status)
		with open('Media/' + linkpath, 'wb') as f:
			f.write(response.content)


	#Create Copy of Json With Links Replaced
	updateStatus(username, "Creating Local Copy Of File...", status)
	localfile = open("local%sAnswers%s.json" % (username, time.strftime("%Y%m%d-%H%M%S")), 'w')

	localJson = re.split(r'(https?://[^ ]*?\.curiouscat.qa/.+?)"', jsonraw)
	localJson = ''.join(['CCArchive%s/Media/%s"' % (username, re.sub('(https?:/?/?[^ ]*?\.curiouscat.qa)|/', '', string)) if re.match(r'(https?://[^ ]*?\.curiouscat.qa/.+?)', string) != None else string for string in localJson])

	localfile.write(localJson)
	localfile.close()
	status['_progress_counter'] += 1
	updateStatus(username, None, status)
	return



def updateStatus(username, Message, statusObj):
	if Message == None:
		del statusObj[username]
	else:
		statusObj[username] = Message

	if not args['verbose']:
		os.system('cls' if os.name == 'nt' else 'clear')

	print("%d/%d Users Archived" % (statusObj['_progress_counter'], len(usernames))) #, end="\r")
	#For Each Current Process Print
	for user in statusObj.keys():
		if user != '_progress_counter':
			print("%s: %s" % (user, statusObj[user]))
	# "%s: (Downloading Posts [%x/%y]|Extracting Links From Json|Downloading Images [%x/%y]|Saving Json)"
	return

if __name__ == '__main__':
	from multiprocessing import Pool, Manager



	manager = Manager()
	status = manager.dict()
	status['_progress_counter'] = 0

	userdata = [(username, status) for username in usernames]

	#If Not Set, Confirm Local Downloads
	while downloadLocal == None:
		yesno = input("Would you like to download all media attached to the CuriousCat Profile [y/n]: ")
		if yesno.lower() == "yes" or yesno.lower() == "y":
			downloadLocal = True
		if yesno.lower() == "no" or yesno.lower() == "n":
			print("Please view the json file using the provided viewer.html file.")
			downloadLocal = False
		pass


	print("Downloading Archives For %d Users" % len(usernames))

	try:
		pool = Pool(processes=args['concurrentDownloads'])
		ts = pool.map(downloadUserAnswers, userdata)
	except KeyboardInterrupt:
		pool.close()
		pool.terminate()
		pool.join()
		print('Exited By User')
		quit()

	print("Archives can now be viewed using viewer.html")
