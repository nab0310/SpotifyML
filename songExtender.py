import pandas as pd #Dataframe, Series
import numpy as np

import io
import sys, getopt

import spotipy
import spotipy.util as util
from spotipy.oauth2 import SpotifyClientCredentials 
import random
import networkx as nx

import os

import config

NUMBER_OF_JUMPS = 30

def handle_spotify_login():
	os.environ['SPOTIPY_CLIENT_ID'] = config.client_id
	os.environ['SPOTIPY_CLIENT_SECRET'] = config.client_secret
	os.environ['SPOTIPY_REDIRECT_URI'] = "http://localhost:8888"
	
	username =''

	client_credentials_manager = SpotifyClientCredentials(client_id=config.client_id, client_secret=config.client_secret) 
	sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

	scope = 'user-library-read playlist-read-private user-read-recently-played user-read-playback-state user-modify-playback-state'
	token = util.prompt_for_user_token(username, scope)

	if token:
		sp = spotipy.Spotify(auth=token)
	else:
		print("Can't get token for", username)
		
	return sp

sp = handle_spotify_login()

def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":  
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")

def euclidian_distance(s1, s2):
    return np.linalg.norm(s1-s2)

def weighted_euclidian_distance(s1,s2,w):
    q = s1-s2
    return np.sqrt((w*q*q).sum())

def calucate_distance(seg1, seg2):
    pitch_dist = euclidian_distance(np.array(seg1["pitches"]),np.array(seg2["pitches"]))
    timbre_dist = weighted_euclidian_distance(np.array(seg1["timbre"]), np.array(seg2["timbre"]),1)
    start_loudness_dist = abs(seg1["loudness_start"] - seg2["loudness_start"])
    max_loudness_dist = abs(seg1["loudness_max"] - seg2["loudness_max"])
    duration_dist = abs(seg1["duration"] - seg2["duration"])
    confidence_dist = abs(seg1["confidence"] - seg2["confidence"])
    distance = timbre_dist + pitch_dist * 10 + start_loudness_dist + max_loudness_dist + duration_dist * 100 + confidence_dist
    return distance
    
def getAnalysisForTrack(songID):
    return sp.audio_analysis("3m9eTtBtU0xxJndQRz9MOr")
    
def averageSegments(segmentsToAvg):
    pitches = [0,0,0,0,0,0,0,0,0,0,0,0]
    timbre = [0,0,0,0,0,0,0,0,0,0,0,0]
    start_loudness = 0
    max_loudness = 0
    duration = 0
    confidence = 0
    for segment in segmentsToAvg:
        pitches += np.array(segment["pitches"])
        timbre += np.array(segment["timbre"])
        start_loudness += segment["loudness_start"]
        max_loudness += segment["loudness_max"]
        duration += segment["duration"]
        confidence += segment["confidence"]
    averagePitches = (pitches) / len(segmentsToAvg)
    averageTimbre = (timbre) / len(segmentsToAvg)
    start_loudness = start_loudness/len(segmentsToAvg)
    max_loudness = max_loudness / len(segmentsToAvg)
    duration = duration /len(segmentsToAvg)
    confidence = confidence /len(segmentsToAvg)
    return {"pitches" : averagePitches, "timbre" : averageTimbre, "loudness_start": start_loudness, "loudness_max": max_loudness, "duration": duration, "confidence": confidence}
    
def computeAverageSegments(analysis, numberOfSegmentsToAvg):
    avgSegments = []
    #Go though the segments by the number we want to average
    for i in range(0, len(analysis["segments"]), numberOfSegmentsToAvg):
        currentSegs = []
        #Add segments we are looking at to array
        for j in range(0, numberOfSegmentsToAvg):
            currentSegs.append(analysis["segments"][i+j])
        #compute the average segment of those
        avgSegment = averageSegments(currentSegs)
        #Initialize vars to compute the closest segment of those averaged
        distanceFromAvg = sys.maxsize
        closestSegmentNumber = 0
        #For the segments, find the closest one to the average one, so we know where to jump
        for j in range(0, numberOfSegmentsToAvg):
            if calucate_distance(currentSegs[j], avgSegment) < distanceFromAvg:
                closestSegmentNumber = j
        avgSegments.append({"closestSegment": i + closestSegmentNumber, "avgSegment": avgSegment})
    return avgSegments
    
def get_closest_segments_avg(segment_number, avgSegments, analysis, numOfSegmentsToGet):
    segment_distance = []
    for segmentObj in avgSegments:
        if segmentObj["closestSegment"] != segment_number:
            distance = calucate_distance(analysis["segments"][segment_number], segmentObj["avgSegment"])
            timeBetween = analysis["segments"][segment_number]["start"] - analysis["segments"][segmentObj["closestSegment"]]["start"]
            if(distance < 80 and distance != 0 and timeBetween > 5):
                segment_distance.append({"distance": distance, "number": segmentObj["closestSegment"]})
    return sorted(segment_distance, key=lambda x: x["distance"], reverse=False)[0:numOfSegmentsToGet]
    
def makeGraphFromAverageSegments(avgSegments, analysis):
    to = []
    segmentsToAddToGraph = []
    fromArray = []
    for i in range(0, len(analysis["segments"])):
        closestSegments = get_closest_segments_avg(i, avgSegments, analysis, 6)
        for segment in closestSegments:
            segmentObject = {"from": i, "to": segment["number"], "distance": segment["distance"]}
            reverseSegmentObject = {"from": segment["number"], "to": i, "distance": segment["distance"]}
            if reverseSegmentObject not in segmentsToAddToGraph:
                segmentsToAddToGraph.append(segmentObject)
    sortedSegments = sorted(segmentsToAddToGraph, key=lambda x: x["distance"], reverse=False)
    randomSortedSegments = random.sample(sortedSegments, NUMBER_OF_JUMPS) 
    wholeFromNumbers = []
    for segment in randomSortedSegments:
        #We want to prevent many jumps in the same second, so add from to a dict and see if the 
        #int value is in the map..... we have to convert from segment numbers to time values
        if int(analysis["segments"][segment["from"]]["start"]) not in wholeFromNumbers:
            wholeFromNumbers.append(int(analysis["segments"][segment["from"]]["start"]))
            to.append(segment["to"])
            fromArray.append(segment["from"])
    print("Length of From Array: " + str(len(fromArray)))
    print("Length of To Array: " + str(len(to)))
    df = pd.DataFrame({'from':fromArray, 'to':to })
    G = nx.from_pandas_edgelist(df, "from", "to")
    return G
    
def makeBranchesToJumpAt(G):
    jumps = []
    sourceVerticies = []
    #print(Counter(fromEdges))
    for u,v in G.edges:
        if random.random() < .5:
            if u not in sourceVerticies:
                jumps.append({"from": u, "to": v})
                sourceVerticies.append(u)
            else:
                if v not in sourceVerticies:
                    jumps.append({"from": v, "to": u})
                    sourceVerticies.append(v)
        else:
            if v not in sourceVerticies:
                jumps.append({"from": v, "to": u})
                sourceVerticies.append(v)
            else:
                if u not in sourceVerticies:
                    jumps.append({"from": u, "to": v})
                    sourceVerticies.append(u)
    return jumps

def playSongAndJumpAtBranches(branches, songID, analysis, G):
    i=0
    newlist = sorted(branches, key=lambda k: k['from']) 
    player = sp._get("me/player")
    if player == None:
        print("Spotify instance unable to be found. Please open spotify on your device or play a track to get started.")
        exit(1)
    sp._put("me/player/play", payload = {"uris":["spotify:track:"+songID], "offset": {"position": 0}})
    sp._put("me/player/repeat?state=track")
    print("We have found " + str(len(branches)) +" branches for your pleasure!")
    print("Here they are: ")
    for branch in newlist:
        print("From " + str(analysis["segments"][branch["from"]]["start"]) + " to " + str(analysis["segments"][branch["to"]]["start"]))
    while True:
        while int(len(newlist)) > 0:
            player = sp._get("me/player")
            if player["progress_ms"] >= analysis["segments"][newlist[i]["from"]]["start"]*1000:
                jump_to = analysis["segments"][newlist[i]["to"]]["start"]*1000
                origin_sec = analysis["segments"][newlist[i]["from"]]["start"]
                dest_sec = analysis["segments"][newlist[i]["to"]]["start"]
                sp._put("me/player/seek?position_ms="+str(int(round(dest_sec * 1000))))
                print("Made jump number "+str(i)+ " out of "+str(len(newlist)))
                print("From " + str(origin_sec) + " to " + str(dest_sec))
                #Remove the branch we jumped from
                del newlist[i]
                #Find next jump point
                #For forward jumps.....
                if origin_sec < dest_sec:
                    #i =  i + 1
                    while  i < len(newlist) - 1 and analysis["segments"][newlist[i]["from"]]["start"] < dest_sec:
                        i = i + 1
                #if we are jumping backwards, we need to iterate backwards through the array and find the 
                #place where this segment fits in.
                else:
                    #i = i - 1
                    if i == len(newlist):
                        i = i -1
                    while i > 0 and analysis["segments"][newlist[i]["to"]]["start"] > dest_sec:
                        i -= 1
                #i=i+1
                if i == len(newlist):
                    i = len(newlist) - 1
        print("Making new branches.")
        branches = makeBranchesToJumpAt(G)
        newlist = sorted(branches, key=lambda k: k['from']) 
        i = 0

def main(argv):
	songName = ''
	artistName = ''
	songID = ''
	try:
		opts, args = getopt.getopt(argv,"hs:a:u:",["song=", "artist=", "uri="])
	except getopt.GetoptError:
		print ("songExtender.py -s '<songName>'")
		print ("songExtender.py --song '<songName>'")
		print ("songExtender.py -a '<artistName>'")
		print ("songExtender.py --artist '<artistName>'")
		print ("songExtender.py -u '<artistName>'")
		sys.exit(2)
	if len(argv) < 2:
		print ("songExtender.py -s '<songName>'")
		print ("songExtender.py --song '<songName>'")
		print ("songExtender.py -a '<artistName>'")
		print ("songExtender.py --artist '<artistName>'")
		print ("songExtender.py -u '<artistName>'")
		sys.exit(2)
	for opt, arg in opts:
		if opt == '-h':
			print ("songExtender.py -s '<songName>'")
			sys.exit()
		elif opt in ("-s", "--song"):
			songName = arg
		elif opt in ("-a", "--artist"):
			artistName = arg
		elif opt in ("-u", "--uri"):
			songID = arg.split(':')[2]
			
	if songName == '' and songID == '':
		print("You must supply a song name or song URI")
		print("Usage: ")
		print ("songExtender.py -s '<songName>'")
		print ("songExtender.py --song '<songName>'")
		print ("songExtender.py -a '<artistName>'")
		print ("songExtender.py --artist '<aritstName>'")
		print ("songExtender.py -u '<artistName>'")
		sys.exit()
		
	if songID == '':
		if artistName != '':
			songResults = sp.search(q="artist:"+artistName+ " track:" + songName, type='track')
		else:
			songResults = sp.search(q='track:' + songName, type='track')
		
		for song in songResults["tracks"]["items"]:
			result = query_yes_no("Did you want to extend the song " + song['name'] + " by " + song["artists"][0]["name"])
			
			if str(result) =="True":
				songID = song['id']
				break
				
		if songID == '':
			#prompt the user to add an artist tag to help us narrow down the search catagory or get the id directly from spotify.
			print("Do you need help?")
			print("Try supplying an artist with the -a or --artist tag. Remeber to enclose your query with ''")
			print("Or you can go get the song URI from spotify and supply it with the -id tag. To get the URI, you should go to Spotify, click on the share for the song you want, and copy the Spotify URI. With the URI in hand, run the program again with songExtender -u spotify:track:<SongID>")
			sys.exit()
		
	analysis = getAnalysisForTrack(songID)
	print("Got Analysis for song with id: "+songID)
	avgSegments = computeAverageSegments(analysis, 4)
	G = makeGraphFromAverageSegments(avgSegments, analysis)
	branches = makeBranchesToJumpAt(G)
	print("Playing song and jumping....")
	print("Enjoy!!")
	print("Use Ctrl + C or Ctrl + Z to quit.")
	playSongAndJumpAtBranches(branches, songID, analysis, G)

if __name__ == "__main__":
   main(sys.argv[1:])

