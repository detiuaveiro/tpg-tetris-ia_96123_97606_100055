import asyncio
from collections import Counter
from copy import copy, deepcopy
import getpass
import json
import os
from shape import L, J, S, Z, I, O, T, Shape

import time

import websockets

import random

WIDTH = 8
HEIGHT = 30

SPEED_RUN = True
PLACEMENTS_LIM = 3      # number of placements to consider for look ahead
LOOK_AHEAD = 1
LOOK_AHEAD_WEIGHT = 0.5
STRATEGY = "clear_lines"  # valid strategies: "clear_lines"


async def agent_loop(server_address="localhost:8000", agent_name="student"):
    async with websockets.connect(f"ws://{server_address}/player") as websocket:

        # Receive information about static game properties
        await websocket.send(json.dumps({"cmd": "join", "name": agent_name}))

        curr_game = None # to decides if a piece is new or not
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

                score = state["score"]

                if is_new_piece:
                    #print("Calculating best move...")
                    tic = time.perf_counter()


                    curr_game = state["game"]
                    curr_piece = state["piece"]
                    next_pieces = state["next_pieces"]


                    if not curr_piece:
                        curr_piece = state["piece"]
                    #print("peca foda:", curr_piece)
                    if curr_piece:
                        curr_shape = identify_shape(curr_piece)
                        #print("Peca Identificada:", curr_shape)

                    best_placements = calculate_piece_plays(curr_shape, curr_game)
                    #print("best placements: " + str(best_placements))

                    bestest_placement = None  # gud variable name
                    for i in range(len(best_placements)):
                        if next_pieces:
                            placement = best_placements[i]
                            next_game = curr_game.copy()
                            next_game.extend(placement[0])
                            _, next_game = count_lines_cleared( next_game )
                            next_placements = calculate_piece_plays(identify_shape(next_pieces[0]), next_game, 1)
                            #print("weird champ", next_placements)
                            best_placements[i] = (best_placements[i][0], next_placements[0][1] * LOOK_AHEAD_WEIGHT)

                        if not bestest_placement or best_placements[i][1] > bestest_placement[1]:
                            bestest_placement = best_placements[i]

                    
                    # get commands to perform best placement
                    inputs = determine_moves(curr_shape, bestest_placement[0])
                    if SPEED_RUN: inputs.append("s")

                    is_new_piece = False
                    #print("inputs to perform: " + str(inputs))
                    toc = time.perf_counter() - tic
                    process_counter += 1
                    times_sum += toc
                    #print("Time to calculate:", toc)


                if state["piece"] is None:
                    is_new_piece = True

                else:
                    key = inputs.pop(0) if inputs else ""
                    #print(f"sent '{key}'")

                    # Send key to game server
                    await websocket.send(
                            json.dumps({"cmd": "key", "key": key})
                        ) 

            except KeyError:
                print("average time:", times_sum/process_counter)
                pass

            except websockets.exceptions.ConnectionClosedOK:
                #print("Server has cleanly disconnected us")
                print(score)
                return


def get_floor(game):
    """ returns an array that contains the y's values on the game for each x """
    higher_pos = [HEIGHT]*WIDTH
    for (x,y) in game:
        if y < higher_pos[x-1]:
            higher_pos[x-1] = y

    return higher_pos


# TODO IMPROVEMENT: rather than counting individual cells as different holes,
# count vertical gaps as one hole, or adjacent empty cells as one hole
# 
#  4 Holes or 3 holes? to be determined
#
#    OOOOO            
#    O OOO
#    O  OO    
#    OOO O
#    O OOO
#    OOOOO

def get_holes(game, floor, mode="individual"):
    """ Get number of holes in game state """
    #print("get_holes - floor:", floor)
    #print("get_holes - game:", game)

    if mode == "individual":
        n_holes = sum( HEIGHT - y for y in floor ) - len(game)
    if mode == "group_vertical":

        new_hole = True

        for i in range(len(floor)):
            for game_y in range(HEIGHT-floor[i]):
                pass
                


    #print("get_holes - number:", n_holes)
    return n_holes

def identify_shape(piece, output = False):
    """ returns what shape the points represent """
    
    #print("Input Peca:", piece)

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



# TODO IMPROVEMENT: only one command can be sent per frame, meaning that moving or rotating a piece will also
# drop it by 1, so take that into account when determining positions, as there may not be enough frames to
# perform the action

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
            inside_pos = deepcopy(pos)

            hadContact = False

            while not hadContact:

                for j in range(rightmost_x): # para cada floor ate o x maximo
                    floor_y = floor[j]
                    for (x,y) in inside_pos: # para cada posicao da peca
                        if x == j+1 and floor_y == y: # ocorreu contato dessa posicao com o chao
                            #print("Found a placement")
                            lst.append([[posx, posy - 1] for (posx, posy) in inside_pos]) # adicionar as pos com y - 1
                            hadContact = True
                            break
                    if hadContact:
                        break
                inside_pos = [[x, y+1] for (x,y) in inside_pos] # se nao houve contato, vamos descer a peca
            
            pos = [[x+1,y] for (x,y) in pos]
            rightmost_x += 1
        copy_shape.rotate()
                
    return lst



# will be used to choose the best possible placement
def evaluate_placement(placement, game, strategy):
    """ Returns a placement's calculated score according to strategy. Higher score means better placement """

    # incentives
    line_clear_value = 3
    value_tetris = True

    # penalties
    holes_value = 20
    height_value = 2#3
    deep_pits_value = 12
    absolute_height_value = 8          # the penalty for letting the building go higher
    global_height_mult = 2              # multiplies height_value and line_clear_value after floor crosses certain threshold
    global_height_threshold = 0        # from what Y does the global_height_mult take effect
    

    # Set value of criteria according to strategy
    if strategy == "clear_lines":
        value_tetris = False
        line_clear_value = 10


    new_game = game + placement     
    lines_cleared, new_game = count_lines_cleared(new_game)
    new_floor = get_floor(new_game)
    n_holes = get_holes(new_game, new_floor)

    highest_point = min(new_floor)
    #height_difference_score = highest_point*2 - max(new_floor) if value_tetris else 0
    height_sum = 0
    deep_pits = 0
    for i in range(len(new_floor)):
        #height_difference_score += new_floor[i] - highest_point
        height_sum += new_floor[i]
        # determine how many pits there are with depth greater than 2, relative to their least tall neighbor
        left_height = new_floor[i-1] if i < 0 else -1
        right_height = new_floor[i+1] if i < len(new_floor) -1 else -1
        deep_pits += new_floor[i] - max(left_height, right_height) > 2

    avg_height = height_sum/WIDTH
    height_difference_score = sum( abs(avg_height - y) for y in new_floor )  # sum of deltas
    

    # print(f"EVALUATE - lines_cleared: {lines_cleared}, after multiplier: {lines_cleared*line_clear_value}")
    # print(f"EVALUATE - n_holes: {n_holes}, after multiplier: {n_holes*holes_value}")
    # print(f"EVALUATE - height_difference_score: {height_difference_score}, after multiplier: {height_difference_score*height_value}")
    # print(f"EVALUATE - deep_pits_score: {deep_pits}, after multiplier: {deep_pits*deep_pits_value}")

    # calculate score
    score = lines_cleared * line_clear_value * ( global_height_mult if highest_point < global_height_threshold else 1 )
    score -= n_holes * holes_value
    score -= height_difference_score * height_value * ( global_height_mult if highest_point < global_height_threshold else 1 )
    score -= deep_pits * deep_pits_value
    score -= (HEIGHT - highest_point) * absolute_height_value

    return score


def calculate_piece_plays(shape, game, quantity=PLACEMENTS_LIM):
    placements = get_possible_placements(shape, get_floor(game))
    best_placements = []

    for placement in placements:
        score = evaluate_placement(placement, game, STRATEGY)

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
