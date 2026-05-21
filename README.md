Its all about an 8bit gaming handheld console that is running micropython on a raspberry pico. 

It use an spi oled 128x64 pixels and 4 buttons.









The structure of the program allows to store multiple games as seperate .py files so not to deal with the main code.



There is a lithium battery and a battery charger inside letting you play on the go.

The charger use as input the vbus pin. Output of the charger is directed to vsys.



A slide main switch to cut off the power of the board is attached on the side.

When powering up a main screen with a list of the games installed is displayed.

You can navigate to the desire game through the main menu and play...

There is increase in the difficulty on every game while playing.



There is a hole to add it in your keys also.

The case is fully 3d printed .

It is specially design not to use any supports or any screws while assembly.

Everything snaps together for the final result.



Some basic soldering skills and computer management skills required for this project.



electronic parts you will need:

1. raspberry pico any of the familly can do the job. i use the pico 2.



2. 4 x Tact Switch 6x6mm 7mm



3. Lithium Battery Charger and Protection Module 1A USB-C - TP4056



4. Slide Switch Mini



5. lithium battery 3.7 v 250mah. size (20mmx30mmx6mm)



6. oled i2c 128x64 display 0,96" screen





Quick tutorial (find the full on the download section.



 gather the materials



         

print the case







assembly the controller screen











solder the parts











upload the programs and test







mount all the parts inside the case











finally!

you are ready to play !





For all games:

There are variables that you can change if needed.

The difficulty increase while playing

There is a game over screen displaying the final score you manage.

While on menu :

Buttons:

right - left : navigate to the games

Up - down : Start the game

Game over screens on the games:

Buttons:

left --> restart game

Up --> return to main menu



1. Tetris

Buttons:

Left --> move left

Right--> move right

Up --> Rotate

Down --> speed up movement

Variables:

SEGMENT_SIZE = 7 (size of the segments of the blocks)

INITIAL_DELAY = 400 (initial delay between movement)

DELAY_STEP = 20 ( step of the speed increase on every speed_delay_interval)

MIN_DELAY = 40 ( the maximum speed that the blocks can reach)

speed_delay_interval= 50000 ( every 50 seconds the speed of movement will increase)



2. Race

 Buttons:

Left --> move left

Right--> move right



Variables:

base_speed = 2 ( what is the starting speed of the cars)

spawn_interval = 20 ( the interval when the new car coming on the top)

speed_delay_interval=50000 ( increase the difficulty on every 50 seconds)

max_maxspeed = 10 (this is the max speed that cars can reach can go up to 12)

min_spawn_interval = 5 (max speed of the interval when the new car coming on the top)



3.Space invanders

Buttons:

Left --> move left

Right--> move right

Variables:

enemy_size = 4

enemy_columns = 8

enemy_rows = 5

movement_y = 3 # vertical movement step in pixels

movedown_interval_time = 1500 ( on every 1,5 second the enemies move down)

next_wave_time = 50 ( reduce movedown_interval_time on every new wave)



4.Snake

Buttons:

Left --> move left

Right--> move right

Up --> move up

Down --> move down

Variables:

GRID_SIZE = 5 (the size of the snake segments)

INITIAL_DELAY = 0.15 # starting “tick” length (seconds)

DELAY_STEP = 0.005 # how much to shave off after every apple(seconds)

MIN_DELAY = 0.04 # don’t let it get faster than this(seconds)
