import asyncio
from collections import Counter
from copy import copy, deepcopy
import getpass
import json
import os
from shape import L, J, S, Z, I, O, T, Shape

import websockets

import random

WIDTH = 8
HEIGHT = 30


async def agent_loop(server_address="localhost:8000", agent_name="student"):
    async with websockets.connect(f"ws://{server_address}/player") as websocket:

        # Receive information about static game properties
        await websocket.send(json.dumps({"cmd": "join", "name": agent_name}))

        previous_game = None # to decides if a piece is new or not
        curr_piece = []


        while True:
            try:
                state = json.loads(
                    await websocket.recv()
                )  # receive game update, this must be called timely or your game will get out of sync with the server
                # state contains: game, piece, next_pieces, game_speed and score

                is_new_piece = state["game"] != previous_game

                if is_new_piece:
                    previous_game = state["game"]
                    curr_piece = state["piece"]
                    floor = get_floor(previous_game)
                
                if not curr_piece:
                    curr_piece = state["piece"]
                    
                if curr_piece:
                    curr_shape = identify_shape(curr_piece)
                    print("Peca Identificada:", curr_shape)
                            

                options = ["a","w","d"]
                #key = random.choice(options)
                key = "a"

                # MAGIC ALGORITHM TO KNOW THE RIGHT KEY
                print("state:", state)
                print("get_floor", floor)    
                # END OF MAGIC ALGORITHM
            
                # Send key to game server
                await websocket.send(
                        json.dumps({"cmd": "key", "key": key})
                    ) 

            except websockets.exceptions.ConnectionClosedOK:
                print("Server has cleanly disconnected us")
                return

def get_floor(game):
    """ returns an array that contains the y's values on the game for each x """
    higher_pos = [HEIGHT]*WIDTH
    for (x,y) in game:
        if y < higher_pos[x-1]:
            higher_pos[x-1] = y

    return higher_pos


def get_holes(game, floor):
    """ Get number of holes in game state """
    n_holes = 0
    for x in range(len(floor)):
        for y in range(29, floor[x]):
            if [x,y] not in game:
                # there is hole
                n_holes += 1
    return n_holes

def identify_shape(piece):
    """ returns what shape the points represent """
    
    print("Input Peca:", piece)

    if piece[0][0] == piece[1][0] == piece[2][0] < piece[3][0]:
        shape = Shape(L)
        shape.set_pos(piece[0][0] - 2, piece[0][1] - 1)
    
    if piece[0][0] == piece[2][0] == piece[3][0] < piece[1][0]:
        shape = Shape(J)
        shape.set_pos(piece[0][0] - 2, piece[0][1] - 1)
 
    if piece[0][0] < piece[1][0] < piece[2][0] < piece[3][0]:
        shape = Shape(I)
        shape.set_pos(piece[0][0], piece[0][1] - 1)

    if piece[0][0] == piece[2][0] < piece[1][0] == piece[3][0]:
        shape = Shape(O)
        shape.set_pos(piece[0][0] - 1, piece[0][1] - 2)
    
    if piece[0][0] == piece[2][0] > piece[1][0] == piece[3][0]:
        shape = Shape(Z)
        shape.set_pos(piece[0][0] - 2, piece[0][1] - 1)

    if piece[0][0] == piece[1][0] < piece[2][0] == piece[3][0]:
        shape = Shape(S)
        shape.set_pos(piece[0][0] - 2, piece[0][1] - 1)

    if piece[0][0] == piece[1][0] == piece[3][0] < piece[2][0]:
        shape = Shape(T)
        shape.set_pos(piece[0][0] - 2, piece[0][1] - 1)


    return shape



def get_possible_placements(piece_shape, floor):
    """ Returns all possible placements for the given piece 
    Returns a list of coordinate lists."""
    lst = []
    copy_shape : Shape = deepcopy(piece_shape)

    for i in range(len(copy_shape.plan)): # para cada rotation
        pos = copy_shape.positions 
        
        minY = HEIGHT
        minX = WIDTH
        maxX = 0
        for (x,y) in pos:
            if y < minY:
                minY = y
            if x < minX:
                minX = x
            if x > maxX:
                maxX =x

        pos = [[x-minX+1,y-minY] for (x,y) in pos]
        # pos = posicoes na extrema esquerda e no topo ☭ 

        while maxX <= WIDTH:

            xs = [None] * WIDTH
            
            for (x,y) in pos:
                if not xs[x-1] or y > xs[x-1]:
                    xs[x-1] = y

            floor_xs = []
            piece_xs = [] # ignora os None
            for j in range(len(xs)):
                if not xs[j]:
                    continue
                
                floor_xs.append(j+1)
                piece_xs.append(xs[j])

            floor_values = []

            for (j,k) in floor:
                if j in floor_xs:
                    floor_values.append(k)



            lowest_pos = [(x, max( y for mx,y in pos if mx==x )) for x in set( x for x,_ in pos )]

            
    return


# will be used to choose the best possible placement
def evaluate_placement(placement, game, strategy):
    """ Returns a placement's calculated score according to strategy. Higher score means better placement """

    
    line_clear_value = 2
    tetris_value = 3
    holes_value = 1
    height_value = 1
    future_value = 0
    

    # Set value of criteria according to strategy
    if strategy == "clear_lines":
        tetris_value = 0
        line_clear_value = 2


    new_game = game + placement     
    lines_cleared, new_game = count_lines_cleared(new_game)
    new_floor = get_floor(new_game)
    n_holes = get_holes(new_game, new_floor)

    highest_point = min([y for _, y in new_floor ])
    height_difference_score = highest_point - max([y for _, y in new_floor])
    for _, y in new_floor:
        height_difference_score += y - highest_point


    # determine possible placements for the next piece and evaluate them,
    # a sort of recursion, with a depth limit
    # future_piece_score = 0


    # calculate score
    score = lines_cleared * line_clear_value
    score -= n_holes * holes_value
    score -= height_difference_score * height_value

    return score



def count_lines_cleared(game):
    """ Return number of lines to be cleared in the given game state, and the new game state after clearing them """
    lines = 0
    new_game = game.copy()

    for item, count in sorted(Counter(y for _, y in game).most_common()):
        if count == HEIGHT:
            new_game = [
                (x, y + 1) if y < item else (x, y)
                for (x, y) in game
                if y != item
            ]  # remove row and drop lines
            lines += 1
    return lines, new_game
    

def determine_moves(piece, placement):
    """ Get list of commands to perform action (e.g. ['w', 'a', 'a']) """
    move_set = []
    _piece = deepcopy(piece)
    piece_coord = _piece.positions
    
    # First, we check if the piece needs rotating
    while(needs_rotating(piece_coord, placement)):
        move_set.append('w')
        _piece.rotate(-1)
        piece_coord = _piece.positions
    
    #R Then, where it needs shifting
    shift = piece_coord[0][0] - placement[0][0]
    letter = 'a' if shift > 0 else 'd'
    shift = abs(shift)
    for i in range(shift):
        move_set.append(letter)
        
    return move_set

def needs_rotating(piece_coord, placement):
    """ Checks if a piece needs to rotate to match a certain palcement """
    piece_coord = sorted(piece_coord, key=lambda x: (x[0], x[1]))
    placement = sorted(placement, key=lambda x: (x[0], x[1]))
    needsRotation = False
    dif = []
    for i in range(4):
        dif.append([[piece_coord[i][0]-placement[i][0],piece_coord[i][1]-placement[i][1]]])
    last = dif[-1]

    for d in range(len(dif)-1):
        if dif[d] != last:
            needsRotation = True
            break
    return needsRotation



# DO NOT CHANGE THE LINES BELLOW
# You can change the default values using the command line, example:
# $ NAME='arrumador' python3 client.py
loop = asyncio.get_event_loop()
SERVER = os.environ.get("SERVER", "localhost")
PORT = os.environ.get("PORT", "8000")
NAME = os.environ.get("NAME", getpass.getuser())
loop.run_until_complete(agent_loop(f"{SERVER}:{PORT}", NAME))
