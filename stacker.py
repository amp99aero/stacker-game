import arcade
import PIL.Image
import numpy as np
import random
from dataclasses import dataclass
from typing import Tuple

from collections import deque
###############################################################################
#piece definition (rel coords to center of piece)
CWM = np.array([[0, -1],[1, 0]])
CCWM = np.array([[0, 1],[-1, 0]])
LV = np.array([[0],[-1]])
RV = np.array([[0],[1]])
UV = np.array([[1],[0]])
DV = np.array([[-1],[0]])

# coordinates are in y, x for working with graphics
#
# ^
# |
# |
# y x ---->

L_COLL = 0B0001
R_COLL = 0B0010
B_COLL = 0B0100
W_COLL = 0B1000


@dataclass
class Piece:
	DEFAULT_ORIENT : np.ndarray
	COLOR : Tuple[int, int, int, int]
#end class
		
PIECES = {'i':Piece(np.array([[0, 0, 0, 0], [0, -1, 1, 2]]), (127,127,255,255)),
		  'o':Piece(np.array([[0, 1, 0, 1], [0, 0, 1, 1]]), (255,255,0,255)),
		  's':Piece(np.array([[0, 0, 1, 1], [0, -1, 0, 1]]), (0,255,0,255)),
		  'z':Piece(np.array([[0, 0, 1, 1], [0, 1, 0, -1]]), (255,0,0,255)),
		  't':Piece(np.array([[0, 0, 0, 1], [0, -1, 1, 0]]), (191,0,255,255)),
		  'j':Piece(np.array([[0, 0, 1, 0], [0, -1, -1, 1]]), (0,0,255,255)),
		  'l':Piece(np.array([[0, 0, 0, 1], [0, -1, 1, 1]]), (255,191,0,255))}

PIECE_KEYS = list(PIECES.keys())
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 800
SCREEN_TITLE = "Stacker"


class MyGame(arcade.Window):
	"""
	Main application class.
	"""

	def __init__(self):

		# Call the parent class and set up the window
		super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)

		t_mask = PIL.Image.open("tetrimo_mask.png")
		self.background = arcade.Texture("background", PIL.Image.open("background.png"))
		self.COMBO_MULTIPLIER = 1.5
		self.BTB_MULTIPLIER = 2.0
		self.LEVEL_MULTIPLIER = 1.1 # multiplies speed, score, and lines to clear

		self.DEFAULT_SPEED = 1.0
		self.MAX_SPEED = 40.0

		self.FIELD_OFFSET_Y = 32
		self.FIELD_OFFSET_X = 32
		self.HOLD_OFFSET_Y = 22*32
		self.HOLD_OFFSET_X = 32
		self.NEXT_OFFSET_Y = 22*32
		self.NEXT_OFFSET_X = 12*32

		self.SCORE_OFFSET_Y = 50
		self.SCORE_OFFSET_X = 12*32
		
		#logic
		self.piece_queue = None

		self.current_piece = None
		self.field = None
		self.current_orientation = None
		self.current_position = None

		self.tetrimos = {k:arcade.Texture(k, self.get_tetrimo(t_mask, k)) for k in PIECE_KEYS}	#for rendering

		

		arcade.set_background_color(arcade.csscolor.BLACK)
	#end def

	def setup(self):
		"""Set up the game here. Call this function to restart the game."""
		# 
		self.field = np.full((25,10), "")
		self.piece_queue = deque(random.sample(PIECE_KEYS, len(PIECE_KEYS)), maxlen=14)
		self.piece_queue.extend(random.sample(PIECE_KEYS, len(PIECE_KEYS)))
		self.drop_speed = 1.0 #tiles per second

		self.current_level = 0 # display +1
		self.lines_to_clear = 10
		self.score = 0
		self.current_combo = 0
		self.btb_stack = 0

		self.collision = False
		self.drop_timer = 1.0 # seconds
		self.soft_drop = False
		self.held_piece = None
		self.speed = self.DEFAULT_SPEED # tiles/s

		self.new_piece()
	#end def

	###################################
	#MODEL

	def accelerate(self):
		self.drop_speed *= self.LEVEL_MULTIPLIER
		if self.drop_speed > self.MAX_SPEED: self.drop_speed = self.MAX_SPEED
	#end def

	def clear_lines(self):
		#set swap sort
		last_index = None
		score = [0, 10, 50, 250, 1000]
		lines_cleared = 0
		for i in range(25):
			if all(self.field[i]):
				lines_cleared += 1
				self.field[i,:] = ""
				if last_index is None:
					last_index = i
				#end if
			elif any(self.field[i]):
				if last_index is not None:
					self.field[last_index] = self.field[i]
					self.field[i,:] = ""
					last_index += 1
				#endif
			else:
				return lines_cleared, score[lines_cleared]
			#end else
		#end for
		return lines_cleared, score[lines_cleared]
	#end def

	def collide(self, position, orientation):
		coll = 0
		posor = position+orientation
		posor = posor[:,np.argsort(posor[0])]

		bottommost = posor.T[0]

		posor = posor[:,np.argsort(posor[1])]
		# sorted by x, (ascending)
		leftmost = posor.T[0]
		rightmost = posor.T[-1]

		#check walls
		if rightmost[1]>9:
			coll |= W_COLL | R_COLL
		elif leftmost[1]<0:
			coll |= W_COLL | L_COLL
		#end elif
		if  bottommost[0]<0:
			coll |= W_COLL | B_COLL
		#end if
		lfield = None
		rfield = None
		anyfield = None
		try:
			lfield = self.field[tuple(leftmost)]
		except:
			pass
		#end except
		try:
			rfield = self.field[tuple(rightmost)]
		except:
			pass
		#end except
		try:
			anyfield = any(self.field[tuple(x)] for x in posor.T)
		except:
			pass
		#end except

		if lfield:
			coll |= L_COLL
		elif rfield:
			coll |= R_COLL
		elif anyfield:
			coll |= B_COLL
		#end elif
		return coll
	#end def

	def finalize_piece(self):
		posor = self.current_position+self.current_orientation
		for tup in posor.T:
			self.field[tuple(tup)] = self.current_piece
		#end for
		lines_cleared, base_score = self.clear_lines()
		score = 0
		# ADD SCORE
		if base_score:
			score = int(self.LEVEL_MULTIPLIER**self.current_level * self.COMBO_MULTIPLIER**self.current_combo * base_score)
			if base_score == 1000:
				score *= self.BTB_MULTIPLIER**self.btb_stack
				self.btb_stack += 1
			else:
				self.btb_stack = 0
			#end else
			self.current_combo += 1
		else:
			self.current_combo = 0
		#end else
		self.score += score

		# ADJUST LEVEL
		self.lines_to_clear -= lines_cleared
		if self.lines_to_clear <= 0:
			self.current_level += 1
			self.lines_to_clear += int(10 * self.LEVEL_MULTIPLIER**(self.current_level+1))
			self.accelerate()
		#end if
		self.current_piece = None
	#end def

	def new_piece(self):
		self.refill_queue()
		self.current_piece = self.piece_queue.popleft()
		self.current_position = np.array([[19],[4]])
		self.current_orientation = PIECES[self.current_piece].DEFAULT_ORIENT
		self.collision = False
		if self.collide(self.current_position, self.current_orientation):
			self.game_over()
		#end if

		self.held = False
		if self.soft_drop:
			self.drop_timer = 1.0/self.MAX_SPEED
		else:
			self.drop_timer = 1.0/self.speed
		#end else
	#end def

	def refill_queue(self):
		if len(self.piece_queue) <=7:
			self.piece_queue.extend(random.sample(PIECE_KEYS, len(PIECE_KEYS)))
		#end if
	#end def

	###################################
	# VIEW

	def ghost(self):
		old_position = self.current_position
		new_position = old_position + DV
		while not self.collide(new_position, self.current_orientation):
			old_position = new_position
			new_position = old_position + DV
		#end while
		return old_position + self.current_orientation
	#end def

	def game_over(self):
		self.setup()
		pass
	#end def

	def on_draw(self):
		"""Render the screen."""

		self.clear()

		#RENDER BACKGROUND
		arcade.draw_texture_rectangle(texture=self.background, center_x=SCREEN_WIDTH/2,center_y=SCREEN_HEIGHT/2,width=SCREEN_WIDTH,height=SCREEN_HEIGHT)
		
		#RENDER EXISTING
		for y, row in enumerate(self.field[:20]):
			for x, tet in enumerate(row):
				tex = self.tetrimos.get(tet, None)
				if tex is not None:
					arcade.draw_texture_rectangle(texture=tex,
												  center_x=x*32+16+self.FIELD_OFFSET_X,
												  center_y=y*32+16+self.FIELD_OFFSET_Y,
												  width=32, height=32)
				#end if
			#end for
		#end for
		
		#RENDER CURRENT PIECE (AND GHOST)
		if self.current_piece:
			ghost_posor = self.ghost()
			for y, x in ghost_posor.T:
				if y<20:
					arcade.draw_rectangle_outline(color=PIECES[self.current_piece].COLOR, center_x=x*32+16+self.FIELD_OFFSET_X,
												  center_y=y*32+16+self.FIELD_OFFSET_Y,
												  width=32, height=32)
			for y, x in (self.current_position+self.current_orientation).T:
				if y<20:
					arcade.draw_texture_rectangle(texture=self.tetrimos[self.current_piece],
												  center_x=x*32+16+self.FIELD_OFFSET_X,
												  center_y=y*32+16+self.FIELD_OFFSET_Y,
												  width=32, height=32)
				#end if
			#end for
		#end if


		#RENDER HOLD
		if self.held_piece:
			for y, x in PIECES[self.held_piece].DEFAULT_ORIENT.T:
				arcade.draw_texture_rectangle(texture=self.tetrimos[self.held_piece],
												  center_x=(x+1)*32+16+self.HOLD_OFFSET_X,
												  center_y=y*32+16+self.HOLD_OFFSET_Y,
												  width=32, height=32)
			#end for
		#end if

		#RENDER NEXT PIECES
		piece = self.piece_queue[0]
		for y, x in PIECES[piece].DEFAULT_ORIENT.T:
			arcade.draw_texture_rectangle(texture=self.tetrimos[piece],
										  center_x=(x-4)*32+16+self.NEXT_OFFSET_X,
										  center_y=y*32+16+self.NEXT_OFFSET_Y,
										  width=32, height=32)
		#end for
		for i in range(1,5):
			piece = self.piece_queue[i]
			for y, x in PIECES[piece].DEFAULT_ORIENT.T:
				arcade.Sprite(texture=self.tetrimos[piece], center_x=(x+1)*32+16+self.NEXT_OFFSET_X, center_y=(y+3*(1-i))*32+16+self.NEXT_OFFSET_Y).draw()
				arcade.draw_texture_rectangle(texture=self.tetrimos[piece],
											  center_x=(x+1)*32+16+self.NEXT_OFFSET_X,
											  center_y=(y+3*(1-i))*32+16+self.NEXT_OFFSET_Y,
											  width=32, height=32)
			#end for
		#end for
		#RENDER LEVEL
		arcade.draw_text(self.current_level+1, self.SCORE_OFFSET_X, self.SCORE_OFFSET_Y+150)
		#RENDER SCORE
		arcade.draw_text(self.score, self.SCORE_OFFSET_X, self.SCORE_OFFSET_Y)
	#end def

	###################################
	# CONTROLLER

	# W
	def hard_drop(self):
		#drop
		while self.move_down(): pass

		self.finalize_piece()
	#end def

	# A
	def move_left(self):
		new_position = self.current_position + LV
		
		if not self.collide(new_position, self.current_orientation):
			self.current_position = new_position
			return True
		#end if
		return False
	#end def

	# S
	def move_down(self):
		new_position = self.current_position + DV

		if not self.collide(new_position, self.current_orientation):
			self.current_position = new_position
			return True
		#end if
		return False
	#end def

	# D
	def move_right(self):
		new_position = self.current_position + RV
		
		if not self.collide(new_position, self.current_orientation):
			self.current_position = new_position
			return True
		#end if
		return False
	#end def

	# Q
	def rotate_CCW(self):
		new_orient = CCWM @ self.current_orientation
		new_position = self.current_position

		coll0 = self.collide(new_position, new_orient)&(L_COLL|R_COLL|B_COLL)
		if coll0:

			if coll0&L_COLL and coll0&R_COLL:
				new_position += UV
			elif coll0&L_COLL:
				new_position += RV
			elif coll0&R_COLL:
				new_position += LV
			#end elif
			coll1 = self.collide(new_position, new_orient) # up one or over one
			if coll1:
				if coll0&L_COLL and coll0&R_COLL:
					return False # up one
				elif coll0&L_COLL:
					if coll1&W_COLL:
						new_position += RV
					else:
						new_position += LV + UV
					#end else
				elif coll0&R_COLL:
					if coll1&W_COLL:
						new_position += LV
					else:
						new_position += RV + UV
					#end else
				#end elif
				if self.collide(new_position, new_orient):
					return False	# temporarily no diagonal moves
				#end if
			#end if
		#end if

		self.current_orientation = new_orient
		self.current_position = new_position
		return True
	#end def

	# E
	def rotate_CW(self):
		new_orient = CWM @ self.current_orientation
		new_position = self.current_position

		coll0 = self.collide(new_position, new_orient)&(L_COLL|R_COLL|B_COLL)
		if coll0:

			if coll0&L_COLL and coll0&R_COLL:
				new_position += UV
			elif coll0&L_COLL:
				new_position += RV
			elif coll0&R_COLL:
				new_position += LV
			#end elif
			coll1 = self.collide(new_position, new_orient) # up one or over one
			if coll1:
				if coll0&L_COLL and coll0&R_COLL:
					return False # up one
				elif coll0&L_COLL:
					if coll1&W_COLL:
						new_position += RV
					else:
						new_position += LV + UV
					#end else
				elif coll0&R_COLL:
					if coll1&W_COLL:
						new_position += LV
					else:
						new_position += RV + UV
					#end else
				#end elif
				if self.collide(new_position, new_orient):
					return False	# temporarily no diagonal moves
				#end if
			#end if
		#end if

		self.current_orientation = new_orient
		self.current_position = new_position
		return True
	#end def

	# LSHIFT
	def hold_piece(self):
		if not self.held:
			piece = self.current_piece
			self.current_piece = self.held_piece
			if self.current_piece:
				self.current_position = np.array([[19],[4]])
				self.current_orientation = PIECES[self.current_piece].DEFAULT_ORIENT
			else:
				self.new_piece()
			#end else
			self.held_piece = piece
			
			if self.soft_drop:
				self.drop_timer = 1.0/self.MAX_SPEED
			else:
				self.drop_timer = 1.0/self.speed
			#end else
			self.held = True
		#end if
	#end def

	def on_key_press(self, key, modifiers):
		if key == arcade.key.W:
			self.hard_drop()
		elif key == arcade.key.A:
			self.move_left()
		elif key == arcade.key.S:
			self.drop_timer = 1.0/self.MAX_SPEED
			self.soft_drop = True
		elif key == arcade.key.D:
			self.move_right()
		elif key == arcade.key.Q:
			self.rotate_CCW()
		elif key == arcade.key.E:
			self.rotate_CW()
		elif key == arcade.key.LSHIFT:
			self.hold_piece()
		#end elif
	#end def

	def on_key_release(self, key, modifiers):
		if key == arcade.key.S:
			self.soft_drop = False
			self.drop_timer = 1.0/self.speed
		#end if
	#end def

	def on_update(self, delta_time):
		self.drop_timer -= delta_time
		if not self.current_piece:
			self.new_piece()
		#end if
		if self.drop_timer<=0:
			if not self.move_down():
				if self.collision:
					self.finalize_piece()
				else:
					self.collision = True
				#end else
			else:
				self.collision = False
			#end else
			if self.soft_drop:
				self.drop_timer = 1.0/self.MAX_SPEED
			else:
				self.drop_timer = 1.0/self.speed
			#end else
		#end if
	#end def
	###################################
	# OTHER

	@staticmethod
	def get_tetrimo(mask, piece):
		return PIL.Image.alpha_composite(PIL.Image.new("RGBA", (32,32), color=PIECES[piece].COLOR), mask)
	#end def
#end class

def main():
	"""Main function"""
	window = MyGame()
	window.setup()
	arcade.run()
#end def


if __name__ == "__main__":
	main()
#end if

#eof