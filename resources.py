key_mapping = {
    "\n": "RETURN",
    "\x1b":"ESCAPE",
    "\t":"TAB",
    343: "NUM_RETURN",
    263: "BACKSPACE",
    "": "BACKSPACE",
    330: "DEL",
    331: "INSERT",
    262: "HOME",
    360: "END",
    338: "PGDOWN",
    339: "PGUP",
    410: "RESIZE",
    258: "DOWN",
    259: "UP",
    260: "LEFT",
    261: "RIGHT"
}

tttc_logo= \
"""                             ____.            
                  ____.----' ,##/      _      _      _        
        ____.----'        ,##" /      | |_   | |_   | |_    ___ 
  _----'              ,###"   /       | __|  | __|  | __|  / __|
 -_              .#####"     /        | |_   | |_   | |_  | (__ 
   '-._      .#######"      /          \__|   \__|   \__|  \___|
       '-..#######"        /         
          \#####"         /         
           \##/,         /          
            \/  '-,     /           
                   '-, /            
                      '             """.split("\n")

auth_text = {
    0: ["", "Please enter your full phone number:", "    %phone%^"],
    1: ["An error occured trying to sign you in.", "Please enter your full phone number:", "    %phone%^"],
    2: ["", "Sending authentification code..."],
    3: ["", "You have been sent a message with", "an activation code. Please provide said code:", "    %code%^"],
    4: ["Incorrect code.", "You have been sent a message with", "an activation code. Please provide said code:", "    %code%^"],
    5: ["", "Signing in..."],
    6: ["", "Two factor authentification is enabled.", "Please provide your password: %pass%^"],
    7: ["Incorrect password.", "Two factor authentification is enabled.", "Please provide your password: %pass%^"],
    8: ["", "Signing in..."]
}
