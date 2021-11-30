import asyncio
from collections import Counter
from copy import deepcopy
import getpass
import json
import os
from shape import L, J, S, Z, I, O, T, Shape

import time

import websockets


WIDTH = 8
HEIGHT = 30

SPEED_RUN = True
#PLACEMENTS_LIM = 3      # number of placements to consider for look ahead
PLACEMENTS_LIM = [2,2,1,0]
LOOK_AHEAD = 2
#LOOK_AHEAD_WEIGHT = 2
LOOK_AHEAD_WEIGHT = [1,2,3,0]
STRATEGY = "clear_lines"  # valid strategies: "clear_lines"

floor_layouts = dict()


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

                if state.get("game") is None: # The dimensions of the game
                    WIDTH = state["dimensions"][0] - 2 # Quando e 10, utilizamos 8 no algoritmo
                    HEIGHT = state["dimensions"][1]
                    continue

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


                    # !!! Recursive Lookahead 
                    #print("=====")
                    bestest_placement = get_best_placement(curr_game,curr_shape,next_pieces,LOOK_AHEAD,0,LOOK_AHEAD_WEIGHT[0],PLACEMENTS_LIM[0])
                    #print(bestest_placement)
                    
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
                print("average time:", times_sum/process_counter)

                #print("floor_layouts:")
                #for key, val in floor_layouts.items():
                #    print(key, ":")
                #    for k, v in val.items():
                #        print("    ", k, ":", v[1])
                    #    for p in v:
                    #        print("        ", p)
                return

def get_best_placement(game, shape, next, lookahead=0, piece_idx=0, weight=1, placement_lim=1000):
    #print('   '*piece_idx,piece_idx, lookahead)
    placements = calculate_piece_plays(shape, game, placement_lim)
    best_placement = None
    if lookahead != 0:
        for placement in placements:
            #print('   '*piece_idx,"placement before:", placement)
            next_game = game + placement[0]
            _, next_game = count_lines_cleared(next_game)
            next_shape = identify_shape(next[piece_idx])
            new_placement = (placement[0], weight*placement[1] + get_best_placement(next_game, next_shape, next, lookahead-1, piece_idx+1, LOOK_AHEAD_WEIGHT[piece_idx+1], PLACEMENTS_LIM[piece_idx+1])[1])
            #print('   '*piece_idx,"placement:", new_placement)
            if not best_placement or new_placement[1] > best_placement[1]:
                best_placement = new_placement
        return best_placement    
    else:
        for placement in placements:
            #print('   '*piece_idx,"terminal placement:", placement)
            if not best_placement or placement[1] > best_placement[1]:
                best_placement = (placement[0], weight*placement[1])
        return best_placement


def get_floor(game):
    """ returns an array that contains the y's values on the game for each x """
    higher_pos = [HEIGHT]*WIDTH
    for (x,y) in game:
        if y < higher_pos[x-1]:
            higher_pos[x-1] = y

    #min_height = min(higher_pos)
    #minimized_floor = tuple( y - min_height for y in higher_pos )
    #floor_layouts[minimized_floor] = floor_layouts.get(minimized_floor, 0) +1

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

    height_offset = min(floor)
    minimized_floor = tuple( y - height_offset for y in floor )

    floor_layout = floor_layouts.get(minimized_floor, None)
    if floor_layout is not None:
        positions = floor_layout.get(tuple(piece_shape.positions), None)
    else:
        positions = None

    if positions:
        positions[1] += 1
        return [ [ [coord[0], coord[1]+height_offset] for coord in pos ] for pos in positions[0] ]
    else:
        lst = []
        cached_lst = []
        copy_shape : Shape = deepcopy(piece_shape)
        # print("nova peca")

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
                cached_pos = [[x, y + height_diff - 1 - height_offset ] for x,y in pos]
                # print("new_pos:", new_pos)
                # print("pos:", pos)
                # print("rightmost_x:", rightmost_x)
                lst.append(new_pos)
                cached_lst.append(cached_pos)
                
                pos = [[x+1,y] for (x,y) in pos]

                rightmost_x += 1
            copy_shape.rotate()
        
        if floor_layout is None:
            floor_layout = dict()
            floor_layouts[minimized_floor] = floor_layout
        floor_layout[tuple(piece_shape.positions)] = [cached_lst, 1]

        return lst



# will be used to choose the best possible placement
def evaluate_placement(placement, game, strategy):
    """ Returns a placement's calculated score according to strategy. Higher score means better placement """

    # incentives
    line_clear_value = 3
    value_tetris = True

    # penalties
    holes_value = 20
    height_value = 4.5
    deep_pits_value = 24
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
