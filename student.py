################################################################################
##                                                                            ##
##   Trabalho por:                                                            ##
##     Lucius Vinicius - 96123                                                ##
##     Diogo Monteiro  - 97606                                                ##
##     Afonso Campos   - 100055                                               ##
##                                                                            ##
##   Special thanks a estes dois grupos, com os quais discutimos o trabalho:  ##
##     Dinis Lei      - 98452                                                 ##
##     Camila Fonseca - 97880                                                 ##
##     Isabel Rosário - 93343                                                 ##
##                                                                            ##
##     Rodrigo Lima   - 98475                                                 ##
##     Diana Oliveira - 98607                                                 ##
##     João Borges    - 98155                                                 ##
##                                                                            ##
################################################################################

import asyncio
from collections import Counter
from copy import deepcopy
import getpass
import json
import os
from shape import L, J, S, Z, I, O, T, Shape

import time

import websockets


SPEED_RUN = True              # when True, use Hard Drop ('s' input)
LOOK_AHEAD = 2                # number of pieces to use for lookahead, where 0 is current piece only
PLACEMENTS_LIM = [2,2,1,0]    # number of placements to consider for look ahead, for each successive piece
LOOK_AHEAD_WEIGHT = [1,1,1,0] # weight given the game state's score after placement, for each successive piece


async def agent_loop(server_address="localhost:8000", agent_name="student"):
    
    async with websockets.connect(f"ws://{server_address}/player") as websocket:

        # Receive information about static game properties
        await websocket.send(json.dumps({"cmd": "join", "name": agent_name}))

        curr_game = None
        curr_piece = []
        inputs = []
        is_new_piece = True
        score = 0

        times_sum = 0
        process_counter = 0
        while True:
            try:
                state = json.loads(
                    await websocket.recv()
                )  # receive game update, this must be called timely or your game will get out of sync with the server
                # state contains: game, piece, next_pieces, game_speed and score

                if state.get("game") is None: # The dimensions of the game
                    global HEIGHT
                    global WIDTH
                    WIDTH = state["dimensions"][0] - 2 # Two of the columns are walls, non-playable area
                    HEIGHT = state["dimensions"][1]
                    continue

                score = state["score"]

                if is_new_piece:
                    tic = time.perf_counter()

                    curr_game = state["game"]
                    curr_piece = state["piece"]
                    next_pieces = state["next_pieces"]

                    if not curr_piece:
                        curr_piece = state["piece"]
                    if curr_piece:
                        curr_shape = identify_shape(curr_piece)
                        if curr_shape is None: continue

                    # !!! Recursive Lookahead 
                    bestest_placement = get_best_placement(curr_game,curr_shape,next_pieces,LOOK_AHEAD,0,LOOK_AHEAD_WEIGHT[0],PLACEMENTS_LIM[0])
                    if bestest_placement is None:
                        continue
                    
                    # get commands to perform best placement
                    inputs = determine_moves(curr_shape, bestest_placement[0])
                    if SPEED_RUN: inputs.append("s")

                    is_new_piece = False
                    toc = time.perf_counter() - tic
                    process_counter += 1
                    times_sum += toc

                else:
                    key = inputs.pop(0) if inputs else ""

                    # Send key to game server
                    await websocket.send(
                            json.dumps({"cmd": "key", "key": key})
                        ) 

                if state["piece"] is None:
                    is_new_piece = True

            except websockets.exceptions.ConnectionClosedOK:
                print(score)
                print("average time:", times_sum/process_counter)
                return


def get_best_placement(game, shape, next, lookahead=0, piece_idx=0, weight=1, placement_lim=1000):
    if shape is None: return None

    placements = calculate_piece_plays(shape, game, placement_lim)
    best_placement = None
    if lookahead != 0:
        for placement in placements:
            next_game = game + placement[0]
            _, next_game = count_lines_cleared(next_game)
            next_shape = identify_shape(next[piece_idx])
            new_placement = (placement[0], weight*placement[1] + get_best_placement(next_game, next_shape, next, lookahead-1, piece_idx+1, LOOK_AHEAD_WEIGHT[piece_idx+1], PLACEMENTS_LIM[piece_idx+1])[1])
            if not best_placement or new_placement[1] > best_placement[1]:
                best_placement = new_placement
        return best_placement    
    else:
        for placement in placements:
            if not best_placement or placement[1] > best_placement[1]:
                best_placement = (placement[0], weight*placement[1])
        return best_placement


def get_floor(game):
    """ returns an array that contains the y's values on the game for each x """
    higher_pos = [HEIGHT]*WIDTH
    for (x,y) in game:
        if y < higher_pos[x-1]:
            higher_pos[x-1] = y

    return higher_pos


def identify_shape(piece, output = False):
    """ returns what shape the points represent """
    
    shape = None

    if piece[0][0] == piece[1][0] == piece[2][0] < piece[3][0]:
        shape = Shape(L)
        shape.set_pos(piece[0][0] - 2, piece[0][1] - 1)
        if output:
            print("Output: L")
    
    if piece[0][0] == piece[2][0] == piece[3][0] < piece[1][0]:
        shape = Shape(J)
        shape.set_pos(piece[0][0] - 2, piece[0][1] - 1)
        if output:
            print("Output: J")
 
    if piece[0][0] < piece[1][0] < piece[2][0] < piece[3][0]:
        shape = Shape(I)
        shape.set_pos(piece[0][0], piece[0][1] - 1)
        if output:
            print("Output: I")

    if piece[0][0] == piece[2][0] < piece[1][0] == piece[3][0]:
        shape = Shape(O)
        shape.set_pos(piece[0][0] - 1, piece[0][1] - 2)
        if output:
            print("Output: O")
    
    if piece[0][0] == piece[2][0] > piece[1][0] == piece[3][0]:
        shape = Shape(Z)
        shape.set_pos(piece[0][0] - 2, piece[0][1] - 1)
        if output:
            print("Output: Z")

    if piece[0][0] == piece[1][0] < piece[2][0] == piece[3][0]:
        shape = Shape(S)
        shape.set_pos(piece[0][0] - 2, piece[0][1] - 1)
        if output:
            print("Output: S")

    if piece[0][0] == piece[1][0] == piece[3][0] < piece[2][0]:
        shape = Shape(T)
        shape.set_pos(piece[0][0] - 2, piece[0][1] - 1)
        if output:
            print("Output: T")

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

        rightmost_x = maxX - minX + 1

        while rightmost_x <= WIDTH: # da esquerda para a direita

            dic = {}
            for (x,y) in pos:
                if x not in dic or dic[x] < y:
                    dic[x] = y

            height_diff = None
            for x,y in dic.items():
                dif = floor[x-1] - y
                if height_diff is None or dif < height_diff:
                    height_diff = dif

            new_pos = [[x,y + height_diff - 1] for x,y in pos]
            lst.append(new_pos)
            
            pos = [[x+1,y] for (x,y) in pos]

            rightmost_x += 1
        copy_shape.rotate()
                
    return lst



# will be used to choose the best possible placement
def evaluate_placement(placement, game):
    """ Returns a placement's calculated score. Higher score means better placement.
        Heuristics and constants based on https://codemyroad.wordpress.com/2013/04/14/tetris-ai-the-near-perfect-player/ ,
        with some of our own experimenting.
    """

    # constants for score calculation
    line_clear_value = 0.76
    height_value = -0.51
    holes_value = -0.356
    bumpiness_value = -0.184

    # get game state after placement
    new_game = game + placement     
    lines_cleared, new_game = count_lines_cleared(new_game)
    new_floor = get_floor(new_game)

    # calculate heuristics
    height_sum = 0
    bumpiness = 0
    for i in range(len(new_floor)):
        height_sum += HEIGHT - new_floor[i]
        if i < len(new_floor)-1:
            bumpiness += abs(new_floor[i]-new_floor[i+1])
    n_holes = height_sum - len(new_game)
    
    # calculate score
    score = lines_cleared * line_clear_value
    score += n_holes * holes_value
    score += height_sum * height_value
    score += bumpiness * bumpiness_value

    return score


def calculate_piece_plays(shape, game, quantity=PLACEMENTS_LIM):
    placements = get_possible_placements(shape, get_floor(game))
    best_placements = []

    for placement in placements:
        score = evaluate_placement(placement, game)

        if len(best_placements) < quantity:
            best_placements.append( (placement, score) )
        else:
            min_score = None
            min_index = None
            for i in range(quantity):
                if min_score is None or best_placements[i][1] < min_score:
                    min_score = best_placements[i][1]
                    min_index = i
            if score > min_score:
                best_placements[min_index] = (placement, score)
    
    return best_placements


def count_lines_cleared(game):
    """ Return number of lines to be cleared in the given game state, and the new game state after clearing them """
    lines = 0
    new_game = game.copy()

    for item, count in sorted(Counter(y for _, y in game).most_common()):
        if count == WIDTH:
            new_game = [
                (x, y + 1) if y < item else (x, y)
                for (x, y) in new_game
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
        _piece.rotate()
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
