from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# 启用 CORS，允许所有来源
CORS(app, resources={r"/*": {"origins": "*"}})
# 配置 SocketIO 支持跨域
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 从环境变量读取视频URL，如果没有设置则使用默认值
VIDEO_URL = os.environ.get('VIDEO_URL', 'https://svip.high21-playback.com/20240721/37526_a7bdcdca/index.m3u8')

# 房间数据结构：{room_id: {'users': set(), 'host': sid, 'host_state': {'time': 0, 'playing': False}}}
rooms = {}

@app.route('/')
def index():
    return render_template('index.html', video_url=VIDEO_URL)

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    
    if room not in rooms:
        rooms[room] = {
            'users': set(),
            'host': None,
            'host_state': {'time': 0, 'playing': False}
        }
    
    rooms[room]['users'].add(request.sid)
    
    # 第一个进入房间的人成为房主
    is_host = False
    if rooms[room]['host'] is None:
        rooms[room]['host'] = request.sid
        is_host = True
    
    # 通知用户加入，并告知是否是房主
    emit('user_joined', {
        'count': len(rooms[room]['users']),
        'is_host': is_host,
        'host_state': rooms[room]['host_state']
    }, room=request.sid)
    
    # 通知房间其他用户有新用户加入
    emit('user_joined_broadcast', {
        'count': len(rooms[room]['users'])
    }, room=room, include_self=False)

@socketio.on('leave')
def on_leave(data):
    room = data['room']
    leave_room(room)
    
    if room in rooms:
        rooms[room]['users'].discard(request.sid)
        
        # 如果房主离开，重新选举房主（选择第一个剩余用户）
        if rooms[room]['host'] == request.sid and rooms[room]['users']:
            rooms[room]['host'] = next(iter(rooms[room]['users']))
            emit('new_host', {'is_host': True}, room=rooms[room]['host'])
        
        if len(rooms[room]['users']) == 0:
            del rooms[room]
        else:
            emit('user_left', {'count': len(rooms[room]['users'])}, room=room)

@socketio.on('sync')
def on_sync(data):
    room = data['room']
    
    # 只有房主可以发送同步指令
    if room in rooms and rooms[room]['host'] == request.sid:
        # 更新房主状态
        rooms[room]['host_state'] = {
            'time': data.get('time', 0),
            'playing': data.get('playing', False)
        }
        # 广播给房间内其他用户（不包括房主自己）
        emit('sync', data, room=room, include_self=False)

@socketio.on('chat_message')
def on_chat_message(data):
    room = data['room']
    message = data.get('message', '')
    username = data.get('username', '匿名用户')
    
    # 广播消息给房间内所有人
    emit('chat_message', {
        'username': username,
        'message': message,
        'timestamp': data.get('timestamp')
    }, room=room)

@socketio.on('disconnect')
def on_disconnect():
    for room in list(rooms.keys()):
        if request.sid in rooms[room]['users']:
            rooms[room]['users'].remove(request.sid)
            
            # 如果房主离开，重新选举房主
            if rooms[room]['host'] == request.sid and rooms[room]['users']:
                rooms[room]['host'] = next(iter(rooms[room]['users']))
                emit('new_host', {'is_host': True}, room=rooms[room]['host'])
            
            if len(rooms[room]['users']) == 0:
                del rooms[room]
            else:
                emit('user_left', {'count': len(rooms[room]['users'])}, room=room)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
