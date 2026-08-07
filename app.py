from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import string
import threading
import time
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ["SECRET_KEY"]
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

rooms = {}
players = {}

WORDS = {
    'easy': ['cat', 'dog', 'sun', 'car', 'tree', 'ball', 'book', 'fish', 'moon', 'star', 'bird', 'home', 'love', 'cake', 
             'rain', 'hat', 'bed', 'cup', 'pen', 'egg', 'ice', 'key', 'box', 'fan', 'map', 'net', 'pot', 'run', 'sit',
             'toy', 'web', 'zoo', 'ant', 'bat', 'fox', 'owl', 'pig', 'rat', 'bee', 'cow', 'fly', 'hen', 'jam', 'leaf',
             'nose', 'rose', 'shoe', 'sock', 'door', 'hand', 'king', 'lock', 'snow', 'wind', 'fire', 'food', 'boat'],
    
    'medium': ['elephant', 'computer', 'guitar', 'butterfly', 'bicycle', 'rainbow', 'penguin', 'volcano', 'mountain', 'dragon',
               'airplane', 'backpack', 'calendar', 'diamond', 'envelope', 'fountain', 'giraffe', 'hamburger', 'internet', 'jellyfish',
               'kangaroo', 'lighthouse', 'microwave', 'notebook', 'octopus', 'parachute', 'question', 'restaurant', 'sandwich', 'telescope',
               'umbrella', 'vampire', 'waterfall', 'xylophone', 'yogurt', 'zipper', 'ambulance', 'basketball', 'chocolate', 'dinosaur',
               'firework', 'gorilla', 'hospital', 'island', 'jungle', 'kitchen', 'laptop', 'monster', 'necklace', 'pyramid',
               'rocket', 'stadium', 'tornado', 'unicorn', 'village', 'wizard', 'mushroom', 'pirate', 'castle', 'treasure'],
    
    'hard': ['microscope', 'helicopter', 'saxophone', 'refrigerator', 'encyclopedia', 'constellation', 'architecture', 'democracy',
             'acrobat', 'algorithm', 'aquarium', 'astronaut', 'atmosphere', 'avalanche', 'barracuda', 'biography', 'blueprint', 'butterfly',
             'camouflage', 'carousel', 'caterpillar', 'cemetery', 'centipede', 'championship', 'chandelier', 'chameleon', 'chiropractor',
             'chrysalis', 'civilization', 'claustrophobia', 'cockatoo', 'crocodile', 'cyclone', 'dalmatian', 'declaration', 'dinosaur',
             'electricity', 'escalator', 'excavator', 'expedition', 'flamingo', 'grasshopper', 'gymnasium', 'hieroglyphics', 'hippopotamus',
             'hologram', 'imagination', 'incubator', 'information', 'inspiration', 'kaleidoscope', 'laboratory', 'leprechaun', 'lieutenant',
             'magnifying', 'marionette', 'marshmallow', 'metabolism', 'metropolitan', 'millennium', 'multiplication', 'observatory',
             'octagonal', 'parallelogram', 'periscope', 'photograph', 'planetarium', 'precipitation', 'pterodactyl', 'refrigerator',
             'rhinoceros', 'silhouette', 'skyscraper', 'spectacular', 'stethoscope', 'thermometer', 'trampoline', 'tyrannosaurus',
             'underground', 'vaccination', 'vegetarian', 'watermelon', 'xylophone', 'harmonica', 'equator', 'glacier']
}

AVATARS = ['😀', '😎', '🤓','🤠', '🥷', '👻', '👽', '🤖', '🎃', '🐱', '🐹', '🐰', '🐻', '🐼','🐯', '🦁','🐵', '🦄', '🐲']

def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_next_drawer(room_code):
    if room_code not in rooms:
        return None
    room = rooms[room_code]
    room['current_drawer_index'] = (room['current_drawer_index'] + 1) % len(room['players'])
    return room['players'][room['current_drawer_index']]

def reveal_hint(room_code):
    """Reveal 1-2 letters after 30 seconds"""
    time.sleep(30)
    
    if room_code not in rooms or not rooms[room_code].get('round_active'):
        return
    
    room = rooms[room_code]
    word = room['current_word']
    word_length = len(word)
    
    positions = list(range(word_length))
    random.shuffle(positions)
    reveal_count = min(2, max(1, word_length // 3))
    
    hint_array = ['_'] * word_length
    for i in range(reveal_count):
        hint_array[positions[i]] = word[positions[i]]
    
    hint = ' '.join(hint_array)
    socketio.emit('word_hint', {'hint': hint}, room=room_code)

def round_timer(room_code):
    """60 second timer for each round"""
    if room_code not in rooms:
        return
        
    room = rooms[room_code]
    room['round_active'] = True
    room['time_remaining'] = 60
    
    hint_thread = threading.Thread(target=reveal_hint, args=(room_code,))
    hint_thread.daemon = True
    hint_thread.start()
    
    for i in range(60, 0, -1):
        if room_code not in rooms or not rooms[room_code].get('round_active'):
            return
        
        rooms[room_code]['time_remaining'] = i
        socketio.emit('timer_update', {'time': i}, room=room_code)
        socketio.sleep(1)
    
    # Time's up
    if room_code in rooms:
        end_round(room_code)

def end_round(room_code):
    if room_code not in rooms:
        return
    
    room = rooms[room_code]
    room['round_active'] = False
    
    if len(room['guessed_players']) > 0 and room['current_drawer'] in room['scores']:
        drawer_points = len(room['guessed_players']) * 10
        room['scores'][room['current_drawer']] += drawer_points
    
    socketio.emit('round_end', {
        'word': room['current_word'],
        'scores': room['scores'],
        'guessed_players': room['guessed_players']
    }, room=room_code)
    
    socketio.sleep(5)
    if room_code in rooms and room['started']:
        start_new_round(room_code)

def start_new_round(room_code):
    if room_code not in rooms:
        return
        
    room = rooms[room_code]
    
    num_players = len(room['players'])
    if num_players <= 4:
        max_rounds = 4
    else:
        max_rounds = num_players
    
    if room['round_number'] >= max_rounds:
        socketio.emit('game_over', {
            'scores': room['scores'],
            'winner': max(room['scores'].items(), key=lambda x: x[1])[0] if room['scores'] else None
        }, room=room_code)
        return
    
    drawer = get_next_drawer(room_code)
    
    if drawer is None:
        return
        
    difficulty = room['difficulty']
    word = random.choice(WORDS[difficulty])
    
    room['current_word'] = word
    room['current_drawer'] = drawer
    room['guessed_players'] = []
    room['round_number'] += 1
    room['round_active'] = True
    
    socketio.emit('new_round', {
        'drawer': drawer,
        'word': word,
        'word_length': len(word),
        'round': room['round_number'],
        'total_rounds': max_rounds
    }, room=room_code)
    
    masked_word = '_ ' * len(word)
    socketio.emit('word_hint', {'hint': masked_word.strip()}, room=room_code)
    
    socketio.emit('clear_canvas', {}, room=room_code)
    
    timer_thread = threading.Thread(target=round_timer, args=(room_code,))
    timer_thread.daemon = True
    timer_thread.start()

@app.route('/')
def index():
    return render_template('index.html', avatars=AVATARS)

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in players:
        player = players[sid]
        room_code = player.get('room')
        
        if room_code and room_code in rooms:
            nickname = player['nickname']
            if nickname in rooms[room_code]['players']:
                rooms[room_code]['players'].remove(nickname)
            if nickname in rooms[room_code]['scores']:
                del rooms[room_code]['scores'][nickname]
            if nickname in rooms[room_code]['avatars']:
                del rooms[room_code]['avatars'][nickname]
            
            socketio.emit('player_left', {
                'nickname': nickname,
                'players': rooms[room_code]['players'],
                'scores': rooms[room_code]['scores']
            }, room=room_code)
            
            if len(rooms[room_code]['players']) == 0:
                rooms[room_code]['round_active'] = False
                del rooms[room_code]
        
        del players[sid]
    print(f'Client disconnected: {sid}')

@socketio.on('create_room')
def handle_create_room(data):
    room_code = generate_room_code()
    nickname = data['nickname']
    avatar = data['avatar']
    
    rooms[room_code] = {
        'players': [nickname],
        'host': nickname,
        'difficulty': 'medium',
        'current_drawer': None,
        'current_drawer_index': -1,
        'current_word': None,
        'guessed_players': [],
        'round_number': 0,
        'started': False,
        'round_active': False,
        'scores': {nickname: 0},
        'avatars': {nickname: avatar}
    }
    
    players[request.sid] = {
        'nickname': nickname,
        'avatar': avatar,
        'room': room_code
    }
    
    join_room(room_code)
    emit('room_created', {'room_code': room_code, 'nickname': nickname, 'avatar': avatar})
    print(f'Room created: {room_code} by {nickname}')

@socketio.on('join_room')
def handle_join_room(data):
    room_code = data['room_code']
    nickname = data['nickname']
    avatar = data['avatar']
    
    if room_code not in rooms:
        emit('error', {'message': 'Room not found'})
        return
    
    if rooms[room_code]['started']:
        emit('error', {'message': 'Game already started'})
        return
    
    rooms[room_code]['players'].append(nickname)
    rooms[room_code]['scores'][nickname] = 0
    rooms[room_code]['avatars'][nickname] = avatar
    
    players[request.sid] = {
        'nickname': nickname,
        'avatar': avatar,
        'room': room_code
    }
    
    join_room(room_code)
    emit('room_joined', {
        'room_code': room_code,
        'nickname': nickname,
        'avatar': avatar,
        'players': rooms[room_code]['players'],
        'host': rooms[room_code]['host'],
        'avatars': rooms[room_code]['avatars']
    })
    
    socketio.emit('player_joined', {
        'nickname': nickname,
        'avatar': avatar,
        'players': rooms[room_code]['players'],
        'avatars': rooms[room_code]['avatars']
    }, room=room_code)
    
    print(f'{nickname} joined room {room_code}')

@socketio.on('set_difficulty')
def handle_set_difficulty(data):
    if request.sid not in players:
        return
        
    room_code = players[request.sid]['room']
    nickname = players[request.sid]['nickname']
    
    if room_code in rooms and rooms[room_code]['host'] == nickname:
        rooms[room_code]['difficulty'] = data['difficulty']
        socketio.emit('difficulty_changed', {'difficulty': data['difficulty']}, room=room_code)

@socketio.on('start_game')
def handle_start_game():
    if request.sid not in players:
        return
        
    room_code = players[request.sid]['room']
    nickname = players[request.sid]['nickname']
    
    if room_code in rooms and rooms[room_code]['host'] == nickname and len(rooms[room_code]['players']) >= 2:
        rooms[room_code]['started'] = True
        socketio.emit('game_started', {
            'avatars': rooms[room_code]['avatars']
        }, room=room_code)
        start_new_round(room_code)
        print(f'Game started in room {room_code}')

@socketio.on('draw')
def handle_draw(data):
    if request.sid not in players:
        return
        
    room_code = players[request.sid]['room']
    nickname = players[request.sid]['nickname']
    
    if room_code in rooms and rooms[room_code]['current_drawer'] == nickname:
        emit('draw', data, room=room_code, include_self=False)

@socketio.on('shape')
def handle_shape(data):
    if request.sid not in players:
        return
        
    room_code = players[request.sid]['room']
    nickname = players[request.sid]['nickname']
    
    if room_code in rooms and rooms[room_code]['current_drawer'] == nickname:
        emit('shape', data, room=room_code, include_self=False)

@socketio.on('fill')
def handle_fill(data):
    if request.sid not in players:
        return
        
    room_code = players[request.sid]['room']
    nickname = players[request.sid]['nickname']
    
    if room_code in rooms and rooms[room_code]['current_drawer'] == nickname:
        emit('fill', data, room=room_code, include_self=False)

@socketio.on('clear_canvas')
def handle_clear_canvas():
    if request.sid not in players:
        return
        
    room_code = players[request.sid]['room']
    nickname = players[request.sid]['nickname']
    
    if room_code in rooms and rooms[room_code]['current_drawer'] == nickname:
        emit('clear_canvas', {}, room=room_code)

@socketio.on('chat_message')
def handle_chat_message(data):
    if request.sid not in players:
        return
        
    room_code = players[request.sid]['room']
    nickname = players[request.sid]['nickname']
    message = data['message'].strip()
    
    if room_code not in rooms:
        return
        
    room = rooms[room_code]
    
    if room['current_drawer'] != nickname and nickname not in room['guessed_players'] and room.get('round_active'):
        if message.lower() == room['current_word'].lower():
            room['guessed_players'].append(nickname)
            points = max(100 - (len(room['guessed_players']) - 1) * 15, 10)
            room['scores'][nickname] += points
            
            socketio.emit('correct_guess', {
                'nickname': nickname,
                'points': points,
                'scores': room['scores']
            }, room=room_code)
            
            if len(room['guessed_players']) == len(room['players']) - 1:
                room['round_active'] = False
                end_round(room_code)
            return
    
    socketio.emit('chat_message', {
        'nickname': nickname,
        'message': message,
        'avatar': players[request.sid]['avatar']
    }, room=room_code)
    
@app.route("/health")
def health():   
    return {
                "status": "UP",
                "service": "word-guessing-game"
            }, 200

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0',allow_unsafe_werkzeug=True, port=5000)
    
