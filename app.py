from pymongo import MongoClient
from datetime import datetime
import uuid
import re
from flask import Flask, redirect, url_for, render_template, request


def readDbConfigFile():
	global conn_str
	global schema_name
	
	with open("database.config", "r") as f:
		content = f.readlines()
		
		for line in content:
			if line.startswith("connection_string"):
				conn_str = re.sub('connection_string\s+=\s+', '', line).strip()
			
			elif line.startswith("schema_name"):
				schema_name = re.sub('schema_name\s+=\s+', '', line).strip()
				
			else:
				None

app = Flask(__name__)				
conn_str = ""
schema_name = ""

readDbConfigFile()

client = MongoClient(conn_str)
db = client[schema_name]
logged_in_username = "UNKNOWN"

			
@app.route("/")
def index(): 
	global logged_in_username

	# get usernames
	user_results = db.users.find( { '$query': {}, '$orderby': { 'username' : 1 } } )
	usernames = []
	for doc in user_results:
		usernames.append(doc["username"])
	
	request_username = request.args.get("loggedinuser")
	
	# check login username exists
	if request_username != None:
	
		# check login username is registered
		users_found = db.users.find( { 'username' : request_username } )
		
		if users_found.count() != 0:
			logged_in_username = request_username
		else:
			logged_in_username = "UNKNOWN"
			return redirect(url_for("index"))
	
	return render_template("index.html", logged_in_username = logged_in_username, all_usernames = usernames)


@app.route("/login")
def loginAsUser():
	uname = request.args.get("username")
	logged_in_username = uname
	return redirect(url_for("index", loggedinuser=logged_in_username))
	
@app.route("/logout")
def logout():
	global logged_in_username
	logged_in_username = "UNKNOWN"
	return redirect(url_for("index"))

@app.route("/add")
def addUser():
	uname = request.args.get("username")
	user_results = db.users.find({'username': uname})
	
	if user_results.count() == 0:
		db.users.insert_one({'username': uname, 'friends' : []})

	return redirect(url_for("index"))

@app.route("/delete")
def deleteUser():
	uname = request.args.get("username")

	# delete user
	db.users.delete_one({'username': uname})
		
	# delete from friends
	friend_results = db.users.find(
		{
			'friends': { 
				'$elemMatch': {
					'$eq': {'friend_username': uname}
				}
			}
		}
	)
	
	for friend in friend_results:
		db.users.update_one(
			{'username': friend['username']},
			{'$pull': {
						'friends': {'friend_username': uname}
					  }
			}
		)
	
	# delete likes
	db.likes.delete_many(
		{'liking_user': uname}
	)
	
	# delete comments
	db.comments.delete_many(
		{'username': uname}
	)
	
	# delete photos
	db.photos.delete_many(
		{'username': uname}
	)
	
	if logged_in_username == uname:
		return redirect(url_for("logout"))
	else:
		return redirect(url_for("index"))

@app.route("/addfriend")
def addFriend():
	uname = request.args.get("username")
	
	user_results = db.users.find(
			{
				'username': uname, 
				'friends': { 
					'$elemMatch': {
						'$eq': {'friend_username': logged_in_username}
					}
				}
			}
	)
	
	if user_results.count() == 0:
		
		db.users.update_one(
			{'username': uname},
			{'$push': {
						'friends': {'friend_username': logged_in_username}
					  }
			}
		)
		
		db.users.update_one(
			{'username': logged_in_username},
			{'$push': {
						'friends': {'friend_username': uname}
					  }
			}
		)

	return redirect(url_for("user_page", username=uname))

@app.route("/unfriend")
def unfriend():
	uname = request.args.get("username")
	
	user_results = db.users.find(
			{
				'username': uname, 
				'friends': { 
					'$elemMatch': {
						'$eq': {'friend_username': logged_in_username}
					}
				}
			}
	)
	
	if user_results.count() != 0:
		
		db.users.update_one(
			{'username': uname},
			{'$pull': {
						'friends': {'friend_username': logged_in_username}
					  }
			}
		)
		
		db.users.update_one(
			{'username': logged_in_username},
			{'$pull': {
						'friends': {'friend_username': uname}
					  }
			}
		)
	return redirect(url_for("user_page", username=uname))

	
# get likes of comments or photos
def getLikes(type, item_id, detailed = False):
	if type == 'C':
		cursor = db.likes.find({ 
			'$query': {
				'type': 'C', 
				'item_id': item_id
			}, 
			'$orderby': { 
				'like_time' : -1 
				} 
		})
		
		likes = []
		
		for item in cursor:
			if detailed:
				likes.append(item)
			else:
				likes.append(str(item['liking_user']))
			
			
		return likes
	
	elif type == 'P':
		cursor = db.likes.find({ 
			'$query': {
				'type': 'P', 
				'item_id': item_id
			}, 
			'$orderby': { 
				'like_time' : -1 
				} 
		})
		
		likes = []
		
		for item in cursor:
			if detailed:
				likes.append(item)
			
			else:
				likes.append(str(item['liking_user']))
			
		return likes
	
	else:
		return None


# get comment_data, comment_likes
def getComments(username):

	user_comments = db.comments.find({
		'$query': {
				'username': username
			}, 
			'$orderby': { 
				'comment_time' : -1 
				} 
	})
	
	comment_data = []
	
	for uc in user_comments:
		comment_data.append( (uc, getLikes('C', uc["comment_id"])) )
	
	return comment_data
	
	
# get photo_data, photo_likes
def getPhotos(username):
	user_photos = db.photos.find({
		'$query': {
				'username': username
			}, 
			'$orderby': { 
				'photo_time' : -1 
				} 
	})
	
	photo_data = []
	
	for up in user_photos:
		photo_data.append( (up, getLikes('P', up["photo_id"])) )
	
	return photo_data

# get friends
def getFriends(user):
	
	friends = []
	
	for uf in user['friends']:
		friends.append( str(uf['friend_username']) )
	
		
	return sorted(friends)
	
@app.route("/user/<username>")
def user_page(username):
	global logged_in_username
	user_results = db.users.find({'username': username})
	data = {}
	
	if user_results.count() == 0:
		data["user_exists"] = False
		data["logged_in_username"] = logged_in_username
	else:
		data["user_exists"] = True
		data["user_data"] = user_results[0]
		data["user_friends"] = getFriends(user_results[0])
		data["user_photos"] = getPhotos(username)
		data["user_comments"] = getComments(username)
		data["logged_in_username"] = logged_in_username
		
	return render_template("userprofile.html", profile_data = data)



@app.route("/changeprofilephoto")
def makeProfilePhoto():
	request_username = request.args.get("username")
	request_photoid = request.args.get("photoid")
	
	photo_results = db.photos.find({
		'username': request_username,
		'photo_id': request_photoid
	})
	
	if photo_results.count() != 0:
		db.users.update_one({
			'username': request_username
			},{
				'$set': {
					'profile_photo_id' : photo_results[0]['photo_id'],
					'profile_photo_url': photo_results[0]['photo_url']
					}
			}
		)
				
		return redirect(url_for("user_page", username=request_username))
		
	else:
		return redirect(url_for("index"))

@app.route("/addphoto")
def addPhoto():
	request_username = request.args.get("username")
	request_photourl = request.args.get("photourl")

	user_results = db.users.find({'username': request_username})
	
	if logged_in_username == request_username and user_results.count() != 0:
		generated_photo_id = str(uuid.uuid4())
		
		db.photos.insert_one({
			'photo_id': generated_photo_id,
			'photo_url': request_photourl,
			'photo_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			'username': request_username
		});
		
		db.users.update_one({
			'username': request_username
			},{
				'$push': {
					'photos':  {
						'photo_id': generated_photo_id
						}
					}
			}
		)
		return redirect(url_for("user_page", username=request_username))
	
	elif logged_in_username != request_username and user_results.count() != 0:
		return redirect(url_for("user_page", username=request_username))
	
	else:
		return redirect(url_for("index"))
		
		

@app.route("/addcomment")
def addComment():
	global logged_in_username
	request_username = request.args.get("username")
	request_comment = request.args.get("comment")

	user_results = db.users.find({'username': request_username})
	
	if logged_in_username == request_username and user_results.count() != 0:
		generated_comment_id = str(uuid.uuid4())
		
		db.comments.insert_one({
			'comment_id': generated_comment_id,
			'username': logged_in_username,
			'comment_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			'comment_text': request_comment
		});
		
		return redirect(url_for("user_page", username=request_username))
	
	elif logged_in_username != request_username and user_results.count() != 0:
		return redirect(url_for("user_page", username=request_username))
	
	else:
		return redirect(url_for("index"))

@app.route("/likedislikephoto")
def likeDislikePhoto():
	global logged_in_username
	request_username = request.args.get("username")
	request_photoid = request.args.get("photoid")

	photo_results = db.photos.find({
		'username': request_username,
		'photo_id': request_photoid
	})
	
	like_results = db.likes.find({
		'liking_user': logged_in_username,
		'item_id': request_photoid,
		'type': 'P'
	})
	
	if photo_results.count() != 0:

		if like_results.count() == 0:
			db.likes.insert_one({
				'liking_user': logged_in_username,
				'like_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
				'type': 'P',
				'item_id': request_photoid
			});
		
		elif like_results.count() == 1:
			db.likes.delete_one({
				'liking_user': logged_in_username,
				'type': 'P',
				'item_id': request_photoid
			});
		
		else:
			None
		
		return redirect(url_for("user_page", username=request_username))
		
	else:
		return redirect(url_for("index"))
	

@app.route("/likedislikecomment")
def likeDislikeComment():
	global logged_in_username
	request_username = request.args.get("username")
	request_commentid = request.args.get("commentid")

	comment_results = db.comments.find({
		'comment_id': request_commentid
	})
	
	like_results = db.likes.find({
		'liking_user': logged_in_username,
		'item_id': request_commentid,
		'type': 'C'
	})
	
	if comment_results.count() != 0:
		if like_results.count() == 0:
			db.likes.insert_one({
				'liking_user': logged_in_username,
				'like_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
				'type': 'C',
				'item_id': request_commentid
			});
			
		elif like_results.count() == 1:
			db.likes.delete_one({
				'liking_user': logged_in_username,
				'type': 'C',
				'item_id': request_commentid
			});
		
		else:
			None
		
		return redirect(url_for("user_page", username=request_username))
		
	else:
		return redirect(url_for("index"))

	
		
if __name__ == "__main__":
	#print getPhotos('legolas')
	app.run(debug = True)
