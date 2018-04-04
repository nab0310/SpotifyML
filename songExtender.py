import pandas as pd #Dataframe, Series
import numpy as np

import io
import sys, getopt

import spotipy
import spotipy.util as util
sp = spotipy.Spotify() 
from spotipy.oauth2 import SpotifyClientCredentials 
import random
import networkx as nx

import os


os.environ['SPOTIPY_CLIENT_ID'] = "0cadd882a6ab4ff485c80b8b02aa3b0c"
os.environ['SPOTIPY_CLIENT_SECRET'] = "04d0f737e18a4a92abee1da25d70766b"
os.environ['SPOTIPY_REDIRECT_URI'] = "http://localhost:8888"


cid ="0cadd882a6ab4ff485c80b8b02aa3b0c" 
secret = "04d0f737e18a4a92abee1da25d70766b"
username = ""

client_credentials_manager = SpotifyClientCredentials(client_id=cid, client_secret=secret) 
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

scope = 'user-library-read playlist-read-private user-read-recently-played user-read-playback-state user-modify-playback-state'
token = util.prompt_for_user_token(username, scope)

if token:
    sp = spotipy.Spotify(auth=token)
else:
    print("Can't get token for", username)

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

def euc_distance(s1, s2):
    return np.linalg.norm(s1-s2)
def weighted_euc_distance(s1,s2,w):
    q = s1-s2
    return np.sqrt((w*q*q).sum())
def calucate_distance(seg1, seg2):
    pitch_dist = euc_distance(np.array(seg1["pitches"]),np.array(seg2["pitches"]))
    timbre_dist = weighted_euc_distance(np.array(seg1["timbre"]), np.array(seg2["timbre"]),1)
    start_loudness_dist = abs(seg1["loudness_start"] - seg2["loudness_start"])
    max_loudness_dist = abs(seg1["loudness_max"] - seg2["loudness_max"])
    duration_dist = abs(seg1["duration"] - seg2["duration"])
    confidence_dist = abs(seg1["confidence"] - seg2["confidence"])
    distance = timbre_dist + pitch_dist * 10 + start_loudness_dist + max_loudness_dist + duration_dist * 100 + confidence_dist
    return distance
def get_top_four_closest_segments(segment_number, analysis):
    segment_distance = []
    for i in range(0, len(analysis["segments"])):
        if i != segment_number:
            distance = calucate_distance(analysis["segments"][segment_number], analysis["segments"][i])
            if(distance < 50 and distance != 0):
                segment_distance.append({"distance": distance, "number": i})
    return sorted(segment_distance, key=lambda x: x["distance"], reverse=False)[0:4]
def getAnalysisForTrack(songID):
    return sp.audio_analysis("3m9eTtBtU0xxJndQRz9MOr")
def makeGraphFromAnalysis(analysis):
    to = []
    segmentsToAddToGraph = []
    fromArray = []
    for i in range(0, len(analysis["segments"])):
        closestSegments = get_top_four_closest_segments(i, analysis)
        for segment in closestSegments:
            segmentObject = {"from": i, "to": segment["number"], "distance": segment["distance"]}
            reverseSegmentObject = {"from": segment["number"], "to": i, "distance": segment["distance"]}
            if reverseSegmentObject not in segmentsToAddToGraph:
                segmentsToAddToGraph.append(segmentObject)
    sortedSegments = sorted(segmentsToAddToGraph, key=lambda x: x["distance"], reverse=False)
    for segment in sortedSegments:
        to.append(segment["to"])
        fromArray.append(segment["from"])
    fromArray = fromArray[0:20]
    to = to[0:20]
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
def playSongAndJumpAtBranches(branches, songID, analysis):
    i=0
    newlist = sorted(branches, key=lambda k: k['from']) 
    sp._put("me/player/play", payload = {"uris":["spotify:track:"+songID], "offset": {"position": 0}})
    sp._put("me/player/repeat?state=track")
    while i < len(branches):
        player = sp._get("me/player")
        if player["progress_ms"] >= analysis["segments"][newlist[i]["from"]]["start"]*1000:
            jump_to = analysis["segments"][newlist[i]["to"]]["start"]*1000
            sp._put("me/player/seek?position_ms="+str(int(round(jump_to))))
            print("Made jump number "+str(i)+ " out of "+str(len(branches)))
            i=i+1

def main(argv):
	songName = ''
	songID = ''
	try:
		opts, args = getopt.getopt(argv,"hs:",["song="])
	except getopt.GetoptError:
		print ("songExtender.py -s '<songName>'")
		print ("songExtender.py --song '<songName>'")
		sys.exit(2)
	if len(argv) < 2:
		print ("songExtender.py -s '<songName>'")
		print ("songExtender.py --song '<songName>'")
		sys.exit(2)
	for opt, arg in opts:
		if opt == '-h':
			print ("songExtender.py -s '<songName>'")
			sys.exit()
		elif opt in ("-s", "--song"):
			songName = arg
	print ('Song Name is '+ songName)
	
	songResults = sp.search(q='track:' + songName, type='track')
	
	for song in songResults["tracks"]["items"]:
		result = query_yes_no("Did you want to extend the song " + song['name'] + " by " + song["artists"][0]["name"])
		
		if str(result) =="True":
			songID = song['id']
			break
			
	if songID == '':
		#prompt the user to add an artist tag to help us narrow down the search catagory or get the id directly from spotify.
	
	print(songID)

if __name__ == "__main__":
   main(sys.argv[1:])


#Run Function
def run():
    songID = "3m9eTtBtU0xxJndQRz9MOr"
    analysis = getAnalysisForTrack(songID)
    print("Got Analysis for song with id: "+songID)
    G = makeGraphFromAnalysis(analysis)
    print("Found Close Pairs of Beats")
    branches = makeBranchesToJumpAt(G)
    print("Playing song and jumping....")
    print("Enjoy!!")
    playSongAndJumpAtBranches(branches, songID, analysis)

    
#run()
