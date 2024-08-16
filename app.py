from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

rooms = {}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    if room not in rooms:
        rooms[room] = set()
    rooms[room].add(request.sid)
    emit('user_joined', {'count': len(rooms[room])}, room=room)

@socketio.on('leave')
def on_leave(data):
    room = data['room']
    leave_room(room)
    if room in rooms:
        rooms[room].remove(request.sid)
        if len(rooms[room]) == 0:
            del rooms[room]
        else:
            emit('user_left', {'count': len(rooms[room])}, room=room)

@socketio.on('sync')
def on_sync(data):
    room = data['room']
    emit('sync', data, room=room, include_self=False)

@socketio.on('disconnect')
def on_disconnect():
    for room in list(rooms.keys()):
        if request.sid in rooms[room]:
            rooms[room].remove(request.sid)
            if len(rooms[room]) == 0:
                del rooms[room]
            else:
                emit('user_left', {'count': len(rooms[room])}, room=room)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0')