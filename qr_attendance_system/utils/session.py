current_user = None

def login(user):
    global current_user
    current_user = {
        "id": user[0],
        "name": user[1],
        "role": user[2]
    }

def logout():
    global current_user
    current_user = None

