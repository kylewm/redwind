/*jslint vars: true, browser: true, devel: true, indent: 2 */
"use strict";

// Constants and a frame counter
var
  BOARD_ROWS = 20,
  BOARD_COLS = 20,
  TILE_WIDTH = 30,
  TILE_HEIGHT = 30,
  FPS = 30,
  UPDATE_EVERY_MS = 100,
  SPECIALIZATION_SCALE = 2,
  CURRENT_LEVEL_IDX = 0;

var LEVELS = [
  'level01', 'level02', 'level03', 'level04', 'level05', 'level06',
  'level07', 'level08', 'level09', 'level10', 'level11', 'level12',
  'level13', 'level14', 'level15', 'level16', 'level17', 'level18',
  'level19', 'level20', 'level21', 'level22', 'level23', 'level24',
  'level25', 'level26', 'level27', 'level28', 'level29', 'level30'
];

var Entity = {};
Entity.type = 'unknown';
Entity.equals = function (other) {
  return other && this.type === other.type;
};
Entity.toString = function () {
  return "Entity:" + this.type;
};


var Tile = Object.create(Entity);
Tile.toString = function () {
  return "Tile:" + this.type;
};

var Wall = Object.create(Tile);
Wall.type = 'wall';
Wall.spriteName = function () {
  return 'metal.png';
};

var Floor = Object.create(Tile);
Floor.type = 'floor';
Floor.spriteName = function () {
  return 'metalfloor.png';
};

var Bombable = Object.create(Tile);
Bombable.type = 'bombable';
Bombable.spriteName = function () {
  return 'bombable2.png';
};

var Drillable = Object.create(Tile);
Drillable.type = 'drillable';
Drillable.spriteName = function () {
  return 'drillable.png';
};

var Water = Object.create(Tile);
Water.type = 'water';
Water.spriteName = function () {
  return 'water.png';
};

var Lava = Object.create(Tile);
Lava.type = 'lava';
Lava.spriteName = function () {
  return 'lava.png';
};

var Arrow = Object.create(Tile);
Arrow.type = 'arrow';
Arrow.init = function (direction) {
  this.direction = direction;
  return this;
};
Arrow.spriteName = function () {
  return this.direction + '_arrow.png';
};

var Bridge = Object.create(Tile);
Bridge.type = 'bridge';
Bridge.init = function (direction) {
  this.direction = direction;
  return this;
};
Bridge.spriteName = function () {
  var orientation;
  if (this.direction === 'up' || this.direction === 'down') {
    orientation = 'ns';
  }
  else {
    orientation = 'ew';
  }
  return orientation + '_bridge.png';
};

var Start = Object.create(Tile);
Start.type = 'start';
Start.frameno = 0;
(function () {
  var FRAMES = ['start00.png', 'start10.png', 'start15.png', 'start20.png',
                'start25.png', 'start30.png', 'start35.png', 'start40.png',
                'start45.png', 'start50.png', 'start55.png', 'start60.png',
                'start55.png', 'start50.png', 'start45.png', 'start40.png',
                'start35.png', 'start30.png', 'start25.png', 'start20.png',
                'start15.png', 'start10.png', 'start05.png' ];
  Start.spriteName = function () {
    var frame = FRAMES[this.frameno % FRAMES.length];
    this.frameno += 1;
    return frame;
  };
}());

var Finish = Object.create(Tile);
Finish.type = 'finish';
Finish.frameno = 0;
(function () {
  var FRAMES = ['finish00.png', 'finish10.png', 'finish15.png', 'finish20.png',
                'finish25.png', 'finish30.png', 'finish35.png', 'finish40.png',
                'finish45.png', 'finish50.png', 'finish55.png', 'finish60.png',
                'finish55.png', 'finish50.png', 'finish45.png', 'finish40.png',
                'finish35.png', 'finish30.png', 'finish25.png', 'finish20.png',
                'finish15.png', 'finish10.png', 'finish05.png' ];
  Finish.spriteName = function () {
    var frame = FRAMES[this.frameno % FRAMES.length];
    this.frameno += 1;
    return frame;
  };
}());

var Gate = Object.create(Tile);
Gate.type = 'gate';
Gate.init = function (orientation, color) {
  this.orientation = orientation;
  this.color = color;
  return this;
};
Gate.spriteName = function () {
  return this.orientation + '_' + this.color + '_gate.png';
};

var GateSwitch = Object.create(Tile);
GateSwitch.type = 'switch';
GateSwitch.init = function (color, weight, state) {
  this.color = color;
  this.weight = weight;
  this.state = state;
  return this;
};
GateSwitch.spriteName = function () {
  var name = this.color + '_switch_' + this.state;
  if (this.weight === 'heavy') {
    name += '_h';
  }
  name += '.png';
  return name;
};

var Movable = Object.create(Entity);
Movable.animate = true;
Movable.advance = function(game) {};
Movable.checkCollisions = function (game) {};
Movable.frameno = 0;
Movable.msPerFrame = 100;
Movable.spriteSuffix = function () {
  var suffix = '';
  if (this.direction === 'up') {
    suffix += '1';
  } else if (this.direction === 'down') {
    suffix += '0';
  } else if (this.direction === 'left') {
    suffix += '2';
  } else if (this.direction === 'right') {
    suffix += '3';
  }
  if (this.animate) {
    var now = Date.now();
    if (!this.lastUpdate || (now - this.lastUpdate >= this.msPerFrame)) {
      this.frameno += 1;
      this.lastUpdate = now;
    }
    suffix += ['0', '1', '2', '1'][this.frameno % 4];
  } else {
    suffix += '1';
  }
  return suffix;
};
Movable.spriteName = function (game) {
  return this.baseSpriteName(game) + '_' + this.spriteSuffix() + '.png';
};
Movable.baseSpriteName = function (game) {
  return this.type; // by coincidence this is often the same
};
Movable.samePositionAs = function (mov) {
  return UTIL.positionsEqual(this.position, mov.position);
};
Movable.toString = function () {
  return "Movable:" + this.type;
};

var Block = Object.create(Movable);
Block.type = 'block';
Block.checkCollisions = function (game) {
  var that = this;
  var cell = game.board.cellAt(this.position);
  cell.tiles.forEach(function (tile) {
    if (tile.type === 'switch') {
      game.board.openGates(tile.color);
    }
  });
};


var Bot = Object.create(Movable);
Bot.direction = 'down';
Bot.variants = function () {
  return [ Object.create(this) ];
};
Bot.advance = function (game) {
  if (!this.dying) {
    this.position = UTIL.advance(this.position, this.direction);
  }
};
Bot.die = function (game, hitTile, hitMovable) {
  console.debug(this.type + ' is dying after hitting ' + (hitTile || hitMovable).type);
  if (this.advanceTarget) {
    if (this === game.trainHead && this.trainPrevious) {
      this.trainPrevious.advanceTarget = this.advanceTarget;
    }
    else if (!game.trainHead.advanceTarget) {
      game.trainHead.advanceTarget = this.advanceTarget;
    }
  }
  this.dying = true;
};
Bot.diesVersusTile = function (game, cell, tile) {
  return ((tile.type === 'water' || tile.type === 'lava') &&
          !cell.anyTilesOfType('bridge')) || 
    tile.type === 'wall' || tile.type === 'bombable' ||
    tile.type === 'drillable' || tile.type === 'block' ||
    tile.type === 'gate';  
};
Bot.diesVersusMovable = function (game, cell, movable) {
  return movable.type === 'block';
};
Bot.checkCollisions = function (game) {
  var cell = game.board.cellAt(this.position);
  this.checkTileCollisions(game, cell);
  this.checkMovableCollisions(game, cell);
};
Bot.checkTileCollisions = function (game, cell) {
  var that = this;
  cell.tiles.forEach(function (tile) {
    if (tile.type == 'arrow') {
      that.direction = tile.direction;
    }
    if (that.diesVersusTile(game, cell, tile)) {
      that.die(game, tile, null);
    }
    if (tile.type === 'switch' && tile.weight !== 'heavy') {
      game.board.openGates(tile.color);
    }
  });
};

Bot.checkMovableCollisions = function (game, cell) {
  var that = this;
  game.movables.forEach(function (mov) {
    if (that.samePositionAs(mov)
        && that.diesVersusMovable(game, cell, mov)) {
      that.die(game, null, mov);
    }
  });
};

Bot.toString = function () {
  return "Bot:" + this.type + (this.dying ? "|dying" : "");
};


var GenericBot = Object.create(Bot);
GenericBot.type = 'genericbot';
GenericBot.spriteName = function (game) {
  if (this.useAppearanceOf) {
    this.useAppearanceOf.direction = this.direction;
    return this.useAppearanceOf.spriteName(game);
  }
  return Bot.spriteName.call(this, game);
};


var ArrowBot = Object.create(Bot);
ArrowBot.type = 'arrowbot';
ArrowBot.advance = function (game) {
  // pass our advance target back to the previous
  if (game.trainHead) {
    game.trainHead.advanceTarget = this.advanceTarget;
  }
  game.board.cellAt(this.position).removeTilesOfType('arrow');
  game.board.placeTile(Object.create(Arrow).init(this.direction), this.position);
  game.removeMovable(this);
};


var BombBot = Object.create(Bot);
BombBot.type = 'bombbot';
BombBot.checkTileCollisions = function (game, cell) {
  function isBombable(tile) {
    return tile.type === 'bombable';
  }
  function removeBombable(position) {
    var cell = game.board.cellAt(position);
    if (cell && cell.tiles.removeIf(isBombable)) {
      removeBombable({ row: position.row-1, col: position.col });
      removeBombable({ row: position.row+1, col: position.col });
      removeBombable({ row: position.row, col: position.col-1 });
      removeBombable({ row: position.row, col: position.col+1 });
    }
  }
  Bot.checkTileCollisions.call(this, game, cell);
  removeBombable(this.position);
};

var BridgeBot = Object.create(Bot);
BridgeBot.type = 'bridgebot';

BridgeBot.checkTileCollisions = function (game, cell) {
  if ((cell.anyTilesOfType('water') || cell.anyTilesOfType('lava'))
      && !cell.anyTilesOfType('bridge')) {
    // pass our advance target back to the previous
    if (game.trainHead && !game.trainHead.advanceTarget) {
      game.trainHead.advanceTarget = this.advanceTarget;
    }
    var tile = Object.create(Bridge).init(this.direction);
    game.board.placeTile(tile, this.position);
    game.removeMovable(this);
  }
  else {
    Bot.checkTileCollisions.call(this, game, cell);
  }  
};

var TurnBot = Object.create(Bot);
TurnBot.type = 'turnbot';
TurnBot.turnDirection = 'ccw';
TurnBot.variants = function () {
  var variant1 = Object.create(this);
  variant1.turnDirection = 'cw';
  var variant2 = Object.create(this);
  variant2.turnDirection = 'ccw';
  return [ variant1, variant2 ];
};
TurnBot.equals = function (o) {
  return Bot.equals.call(this, o) && this.turnDirection === o.turnDirection;
};
TurnBot.baseSpriteName = function (game) {
  var name = Bot.baseSpriteName.call(this, game) + '_';
  if (this.turnDirection === 'ccw') {
    name += 'left';
  } else {
    name += 'right';
  }
  return name;
};
TurnBot.advance = function (game) {
  var nextPos, nextCell;
  Bot.advance.call(this);
  if (!this.dying) {
    nextPos = UTIL.advance(this.position, this.direction);
    nextCell = game.board.cellAt(nextPos);
    if (nextCell && (nextCell.anyTilesOfType('wall')
                     || nextCell.anyTilesOfType('drillable')
                     || nextCell.anyTilesOfType('bombable'))) {
      if (this.turnDirection === 'ccw') {
        this.direction = this.direction === 'up' ? 'left' : 
          this.direction === 'left' ? 'down' : 
          this.direction === 'down' ? 'right' : 'up';
      } else {
        this.direction = this.direction === 'up' ? 'right' : 
          this.direction === 'right' ? 'down' : 
          this.direction === 'down' ? 'left' : 'up';
      }
    }
  }
};
TurnBot.toString = function () {
  return Bot.toString.call(this) + "|" + this.turnDirection;
};

var SwimBot = Object.create(Bot);
SwimBot.type = 'swimbot';
SwimBot.diesVersusTile = function (game, cell, tile) {
  return (tile.type !== 'water') && Bot.diesVersusTile.call(this, game, cell, tile);
};
SwimBot.baseSpriteName = function (game) {
  var name = Bot.baseSpriteName.call(this, game);
  if (this.position) {
    var cell = game.board.cellAt(this.position);
    if (cell.anyTilesOfType('water') && !cell.anyTilesOfType('bridge')) {
      name += '_under';
    }
  }
  return name;
};

var DrillBot = Object.create(Bot);
DrillBot.type = 'drillbot';
DrillBot.checkTileCollisions = function (game, cell) {
  cell.removeTilesOfType('drillable');
  Bot.checkTileCollisions.call(this, game, cell);
};

var PushBot = Object.create(Bot);
PushBot.type = 'pushbot';

PushBot.advance = function (game) {
  var that = this;
  Bot.advance.call(this, game);
  
  game.movables.forEach(function (mov) {
    if (that.samePositionAs(mov)
        && mov.type === 'block') {
      
      var newpos = UTIL.advance(mov.position, that.direction);
      var newcell = game.board.cellAt(newpos);
      if (!newcell.anyTilesOfType('wall')
          && !newcell.anyTilesOfType('drillable')
          && !newcell.anyTilesOfType('bombable')) {
        mov.position = newpos;
        mov.direction = that.direction;
      }
    }
  });  
};

var CabooseBot = Object.create(Bot);
CabooseBot.type = 'caboosebot';
CabooseBot.checkCollisions = function (game) {
  Bot.checkCollisions.call(this, game);
  if (this.dying) {
    game.lost = true;
  }
};
CabooseBot.checkTileCollisions = function (game, cell) {
  Bot.checkTileCollisions.call(this, game, cell);
  if (!this.dying && cell.anyTilesOfType('finish')) {
    game.won = true;
    this.advancing = false;
  }
};


var BOTS = [
  GenericBot, 
  ArrowBot,
  BombBot,
  BridgeBot,
  TurnBot,
  SwimBot,
  DrillBot,
  PushBot,
  CabooseBot
];

var BOT_BY_TYPE = {};
BOTS.forEach(function (bot) {
  BOT_BY_TYPE[bot.type] = bot;
});

var Cell = {
  init: function() {
    this.tiles = [];
    return this;
  },
  anyTilesOfType: function (type) {
    return this.tiles.some(function (tile) { return tile.type === type; });
  },
  removeTilesOfType: function (type) {
    this.tiles.removeIf(function (tile) { return type === tile.type; });
  }
};

var Board = {
  init: function () {
    this.cells = [];
    return this;
  },
  cellAt: function (position) {
    return this.cells[position.row] &&
      this.cells[position.row][position.col];
  },
  placeTile: function (tile, position) {
    if (!this.cells[position.row]) {
      this.cells[position.row] = [];
    }
    if (!this.cells[position.row][position.col]) {
      this.cells[position.row][position.col] = Object.create(Cell).init();
    }
    this.cells[position.row][position.col].tiles.push(tile);
  },
  openGates: function (color) {
    this.forEachCell(function (position, cell) {
      cell.tiles.removeIf(function (tile) {
        return tile.type === 'gate' && tile.color === color;
      });
    });
  },
  width: function () {
    return this.cells[0].length;
  },
  height: function () {
    return this.cells.length;
  },
  forEachCell: function (fn) {
    var row, col, cell;
    for (row = 0 ; row < this.cells.length ; row += 1) {
      for (col = 0 ; col < this.cells[row].length ; col += 1) {
        fn({ row: row, col: col }, this.cells[row][col]);
      }
    }
  },
  forEachTile: function (fn) {
    this.forEachCell(function (position, cell) {
      cell.tiles.forEach(function (tile) {
        fn(position, tile);
      });
    });
  }

};

var LEVEL_READER = {
  LEVEL_TILE_ENCODINGS: {
    '.': [Floor],
    '0': [Wall],
    '1': [Floor, Bombable],
    '2': [Floor], //unused laserable],
    '4': [Floor, Drillable],
    '5': [Water],
    '6': [Lava],
    '<': [Floor, Object.create(Arrow).init('left')],
    '>': [Floor, Object.create(Arrow).init('right')],
    '^': [Floor, Object.create(Arrow).init('up')],
    'v': [Floor, Object.create(Arrow).init('down')],
    's': [Floor, Start],
    'f': [Floor, Finish],
    '3': [Floor],
    'r': [Floor, Object.create(GateSwitch).init('red', 'normal', 'up')],
    'g': [Floor, Object.create(GateSwitch).init('green', 'normal', 'up')],
    'b': [Floor, Object.create(GateSwitch).init('blue', 'normal', 'up')],
    'o': [Floor, Object.create(GateSwitch).init('orange', 'normal', 'up')],
    'q': [Floor, Object.create(GateSwitch).init('red', 'heavy', 'up')],
    'w': [Floor, Object.create(GateSwitch).init('green', 'heavy', 'up')],
    'a': [Floor, Object.create(GateSwitch).init('blue', 'heavy', 'up')],
    'z': [Floor, Object.create(GateSwitch).init('orange', 'heavy', 'up')],
    'R': [Floor, Object.create(Gate).init('ns', 'red')],
    'G': [Floor, Object.create(Gate).init('ns', 'green')],
    'B': [Floor, Object.create(Gate).init('ns', 'blue')],
    'O': [Floor, Object.create(Gate).init('ns', 'orange')],
    'Q': [Floor, Object.create(Gate).init('ew', 'red')],
    'W': [Floor, Object.create(Gate).init('ew', 'green')],
    'A': [Floor, Object.create(Gate).init('ew', 'blue')],
    'Z': [Floor, Object.create(Gate).init('ew', 'orange')],
    '{': [Floor],
    '}': [Floor],
    '[': [Floor],
    ']': [Floor]
  },

  LEVEL_MOVABLE_ENCODINGS: {
    '3': [Block],
    '{': [], //enemy-left
    '}': [], //enemy-right
    '[': [], //enemy-up
    ']': []  //enemy-down
  },

  read: function (name, game, callback) {
    var that = this;
    UTIL.loadAsset("levels/" + name + ".txt", function (req) {
      that.finish(req.responseText, game, callback);
    });
  },

  finish: function (text, game, callback) {
    var lines = text.split(/\r?\n/);
    var row, col, tiles, ii, jj, movs;

    game.levelInfo = { 
      title: lines[0],
      numberOfBots: Number(lines[1]),
      earnedBots: Number(lines[2]),
      numberOfNewBots: Number(lines[3]),
      description: lines[4]
    };

    for (ii = 5, row = 0; ii < lines.length; ii += 1, row += 1) {
      var line = lines[ii];
      for (col = 0; col < line.length; col += 1) {
        var chr = line.charAt(col);
        var pos = { row: row, col: col };
        tiles = this.LEVEL_TILE_ENCODINGS[chr];
        if (tiles) {
          tiles.forEach( function (tile) {
            var tile = Object.create(tile);
            game.board.placeTile(tile, pos);
            if (tile.type === 'start') {
              game.levelInfo.start = pos;
            }
          });
        }
        movs = this.LEVEL_MOVABLE_ENCODINGS[chr];
        if (movs) {
          movs.forEach( function (mov) {
            var mov = Object.create(mov);
            mov.position = pos;
            mov.direction = 'down';
            game.movables.push(mov);
          });
        }
      }
    }
    callback();
  }
};

var IMAGE_CACHE = {
  init: function (callback) {
    this.images = {};
    this.loadImages(['movables', 'terrain'], ['water', 'lava'], callback);
  },
  loadImages: function (spriteSheets, textures, callback) {
    var that = this,
    countdown = spriteSheets.length + textures.length,
    countdownFn = UTIL.callbackAfterCountdown(countdown, callback);

    spriteSheets.forEach(function (sheet) {
      that.loadSpriteSheet(sheet, countdownFn);
    });
    textures.forEach(function (texture) {
      that.loadTexture(texture, countdownFn);
    });
  },

  loadTexture: function (name, callback) {
    var textureName = name + '.png',
    imgUrl = 'images/' + textureName,
    imgObj = new Image(),
    textureRep = {
      img: imgObj,
      type: 'texture'
    };

    imgObj.onload = callback;
    this.images[textureName] = textureRep;
    imgObj.src = imgUrl;
  },

  loadSpriteSheet: function (name, callback) {
    var that = this,
    jsonUrl = 'images/' + name + '.json',
    imgUrl = 'images/' + name + '.png',
    countdownFn = UTIL.callbackAfterCountdown(2, callback),
    imgObj = new Image();

    //sheetImages[name] = imgObj;
    imgObj.onload = countdownFn;
    imgObj.src = imgUrl;

    UTIL.loadAsset(jsonUrl, function (req) {
      var
      parsed = JSON.parse(req.responseText),
      spriteName,
      spriteRep,
      sprite;

      parsed.frames.forEachEntry(function (spriteName, sprite) {
        spriteRep = {
          x: sprite.frame.x,
          y: sprite.frame.y,
          w: sprite.frame.w,
          h: sprite.frame.h,
          img: imgObj,
          type: 'sprite'
        };
        
        that.images[spriteName] = spriteRep;
      });
      
      console.debug('loaded ' + jsonUrl);
      countdownFn();
    });
  }  
};

var UI = {
  init: function (game) {
    var that = this;
    this.game = game; // the logic

    this.canvas = document.getElementById('game');
    this.ctx = this.canvas.getContext('2d');
    this.ctx.mozImageSmoothingEnabled = false;

    var boardbounds = {
      x: 0,
      y: 0, 
      w: BOARD_COLS * TILE_WIDTH,
      h: BOARD_ROWS * TILE_HEIGHT
    };
    var specbounds = {
      x: boardbounds.x + boardbounds.w,
      y: 0,
      w: 2 * TILE_WIDTH * (SPECIALIZATION_SCALE + 5),
      h: boardbounds.h
    };
    
    this.boardui = Object.create(BoardUI)
      .init(game, this, boardbounds);
    this.specui = Object.create(SpecUI)
      .init(game, this, SPECIALIZATION_SCALE, specbounds);

    this.components = [ this.boardui, this.specui ];
    this.addListeners();

    return this;
  },

  addListeners: function () {
    var that = this;
    this.canvas.addEventListener('mousemove', function (evt) {
      var coords = that.canvas.relMouseCoords(evt);
      for (var ii = 0 ; ii < that.components.length ; ii += 1) {
        var component = that.components[ii];
        if (UTIL.inBounds(component.bounds, coords)
            && component.mouseMoved) {
          component.mouseMoved(coords);
        }
      }
    });
    // mouse clicks will indicate where the train should advance to
    this.canvas.addEventListener('click', function (evt) {
      var coords = that.canvas.relMouseCoords(evt);
      for (var ii = 0 ; ii < that.components.length ; ii += 1) {
        var component = that.components[ii];
        if (UTIL.inBounds(component.bounds, coords)
            && component.mouseClicked) {
          component.mouseClicked(coords);
        }
      }
    }, true);
  },

  draw: function (interp) {
    this.boardui.draw(interp);
    this.specui.draw();
  },

  drawSprite: function (name, posx, posy, xfactor, yfactor) {
    xfactor = xfactor || 1;
    yfactor = yfactor || 1;
    var sprite = IMAGE_CACHE.images[name];
    if (sprite) {
      if (sprite.type === 'texture') {
        this.ctx.drawImage(sprite.img, posx, posy, TILE_WIDTH, TILE_HEIGHT,
                           posx, posy, TILE_WIDTH*xfactor, TILE_HEIGHT*yfactor);
      } else {
        this.ctx.drawImage(sprite.img, sprite.x, sprite.y, sprite.w, sprite.h,
                           posx, posy, sprite.w*xfactor, sprite.h*yfactor);
      }
    }
  }
};

var BoardUI = {
  init: function (game, ui, bounds) {
    this.game = game;
    this.ui = ui;
    this.bounds = bounds;

    return this;
  },

  mouseClicked: function (coords) {
    this.game.clickPosition = {
      row: Math.floor(coords.y / TILE_HEIGHT),
      col: Math.floor(coords.x / TILE_WIDTH)
    };
  },

  mouseMoved: function (coords) {
    this.game.hoverPosition = {
      row: Math.floor(coords.y / TILE_HEIGHT),
      col: Math.floor(coords.x / TILE_WIDTH)
    };
  },

  draw: function (interp) {
    this.drawBoard();
    this.drawMovables(interp);
    this.drawHighlights();
  },

  drawBoard: function () {
    var that = this;
    //console.log("animating this = " + this);
    //console.log("this.board = " + this.board);
    
    this.game.board.forEachTile(function (position, tile) {
      that.ui.drawSprite(tile.spriteName(that.game),
                         position.col * TILE_WIDTH,
                         position.row * TILE_HEIGHT);
    });
  },

  drawMovables: function (interp) {
    var that = this;
    this.game.movables.forEach(function (mov) {
      var row = mov.position.row;
      var col = mov.position.col;

      if (mov.previousPosition) {
        row = row * interp + mov.previousPosition.row * (1 - interp);
        col = col * interp + mov.previousPosition.col * (1 - interp);
      }      
      that.ui.drawSprite(mov.spriteName(that.game),
                         col * TILE_WIDTH,
                         row * TILE_HEIGHT);
    });
  },

  drawHighlights: function () {
    var that = this;
    this.game.board.forEachCell(
      function (position, cell) {
        if (cell.onTrainPath || cell.onLaunchPath) {
          if (cell.onTrainPath) {
            that.ui.ctx.fillStyle = 'rgba(255, 255, 0, 0.25)';
          } 
          else {
            that.ui.ctx.fillStyle = 'rgba(0, 255, 0, 0.25)';            
          }
          that.ui.ctx.fillRect(position.col * TILE_WIDTH,
                               position.row * TILE_HEIGHT, 
                               TILE_WIDTH, TILE_HEIGHT);
        }
      });
  }

};

// ui for choosing specialization
var SpecUI = {

  init: function (game, ui, scale, bounds) {
    this.game = game;
    this.ui = ui;
    this.scale = scale;
    this.bounds = bounds;
    return this;
  },

  draw: function () {
    var earned = this.game.levelInfo.earnedBots;

    this.ui.ctx.clearRect(this.bounds.x, this.bounds.y,
                          this.bounds.w, this.bounds.h);

    for (var ii = 0 ; ii < earned+1 && ii < BOTS.length ; ii += 1) {
      var prototypeBot = BOTS[ii];
      var variants = prototypeBot.variants();
      for (var jj = 0 ; jj < variants.length ; jj++) {
        var posx = this.bounds.x + jj * (TILE_WIDTH * this.scale + 5) + 2;
        var posy = this.bounds.y + ii * (TILE_HEIGHT * this.scale + 5) + 2;
        var bot = variants[jj];
        bot.direction = 'down';
        bot.animate = false;

        this.ui.drawSprite(bot.spriteName(this.game), posx, posy, this.scale, this.scale);
        if (bot.equals(this.game.specialization)) {
          this.ui.ctx.fillStyle = 'rgba(0, 255, 0, 0.1)';
          this.ui.ctx.fillRect(posx, posy,
                               TILE_WIDTH * this.scale,
                               TILE_HEIGHT * this.scale);

          this.ui.ctx.strokeStyle = 'rgb(0, 255, 0)';
          this.ui.ctx.strokeRect(posx, posy, 
                                 TILE_WIDTH * this.scale, 
                                 TILE_HEIGHT * this.scale);
        }
      }
    }
  },

  mouseClicked: function (coords) {
    var earned = this.game.levelInfo.earnedBots;
    for (var ii = 0 ; ii < earned+1 && ii < BOTS.length ; ii += 1) {
      var posy1 = this.bounds.y + ii * (TILE_HEIGHT * this.scale + 5) + 2;
      var posy2 = posy1 + TILE_HEIGHT * this.scale;
      if (coords.y >= posy1 && coords.y <= posy2) {
        var prototypeSpec = BOTS[ii];
        var variants = prototypeSpec.variants();
        
        for (var jj = 0 ; jj < variants.length ; jj += 1) {
          var posx1 = this.bounds.x + jj * (TILE_WIDTH * this.scale + 5) + 2;
          var posx2 = posx1 + TILE_WIDTH * this.scale;
          if (coords.x >= posx1 && coords.x <= posx2) {
            var spec = variants[jj];
            console.log("specializing to: " + spec.toString());
       
            if (spec.equals(this.game.specialization)) {
              this.game.specialization = null;
            }
            else {
              this.game.specialization = spec;
            }
            
          }
        }
      }
    }
  }

};

var Game = {

  init: function (levelIdx) {
    var that = this;
    this.currentLevelIdx = levelIdx || 0;
    this.ui = Object.create(UI).init(this);
    // the game hasn't started until the player has chosen a starting direction
    this.deployed = false;

    this.board = Object.create(Board).init();
    this.movables = [];    

    LEVEL_READER.read(LEVELS[this.currentLevelIdx], this, function () {
      that.ui.draw(0);
      alert(that.levelInfo.title + "\n" + that.levelInfo.description);
      // start the game loop
      that.intervalId = setInterval(UTIL.bind(that, that.mainLoop),
                                    1000 / FPS);
    });
    
    return this;
  },

  stop: function () {
    clearInterval(this.intervalId);
  },

  mainLoop: function () {
    var now = Date.now();
    
    if (!this.lastUpdate || (now - this.lastUpdate) >= UPDATE_EVERY_MS) {
      this.processEvents();
      this.update();
      this.lastUpdate = now;
    }
    // 0 to 1.0 representing the interpolated position between
    // previous and current position
    var interp = (now - this.lastUpdate) / UPDATE_EVERY_MS;
    this.ui.draw(interp);
  },

  removeDead: function ()  {
    var that = this;
    this.movables.forEach(function (mov) {
      if (mov.dying && that.trainHead === mov) {
        that.trainHead = mov.trainPrevious;
      }
    });

    this.movables.removeIf(
      function (mov) { return mov.dying; });
  },

  removeMovable: function (mov) {
    var idx = this.movables.indexOf(mov);
    console.log("removing movable: " + idx);
    this.movables.splice(idx, 1);
  },

  processEvents: function() {
    if (this.clickPosition) {
      var cell = this.board.cellAt(this.clickPosition);
      if (cell.onTrainPath) {
        if (!this.deployed) {
          this.deployed = true;
          this.numberToDeploy = this.levelInfo.numberOfBots;
          this.deployDirection = cell.onTrainPath; // changed from a bool to the deploy direction
          this.launchTarget = this.clickPosition; // temporary
        }
        else {
          this.trainHead.advanceTarget = this.clickPosition;
        }
        this.advancing = true;
      }
      else if (cell.onLaunchPath) {
        this.launchDirection = cell.onLaunchPath; // changed from a bool to the deploy direction
        this.trainHead.advanceTarget = this.clickPosition;
        this.advancing = true;
      }
    }
    this.clickPosition = null;
    this.hoverPosition = null;
    
  },
  
  // update the state of the world
  update: function () {
    this.removeDead();
    this.specializeTrainHeadAppearance();
    this.maybeLaunch();
    this.advance();
    this.maybeDeploy();
    this.maybeStopAdvancing();
    this.calculatePaths();
    this.checkGameOver();
  },

  specializeTrainHeadAppearance: function () {
    if (this.trainHead && this.trainHead !== this.trainCaboose) {
      this.trainHead.useAppearanceOf = this.specialization;
    }
  },

  advance: function () {
    var that = this;
    this.movables.forEach(function (mov) {
      mov.previousPosition = mov.position;
    });
    if (this.deployed && this.advancing) {
      this.movables.forEach(function (mov) { mov.advance(that); });
      this.movables.forEach(function (mov) { mov.checkCollisions(that); });
    }
  },

  maybeStopAdvancing: function () {
    if (this.advancing) {
      for (var ii = 0 ; ii < this.movables.length ; ii += 1) {
        var mov = this.movables[ii];
        if (mov.advanceTarget &&
            UTIL.positionsEqual(mov.position, mov.advanceTarget)) {
          this.advancing = false;
          mov.advanceTarget = null;
        }
      }
    }
  },

  maybeLaunch: function () {      
    if (this.launchDirection && this.trainHead !== this.trainCaboose) {
      var launched = this.trainHead;
      this.trainHead = this.trainHead.trainPrevious;
      
      this.removeMovable(launched);

      var specialized = Object.create(
        this.specialization || GenericBot);
      specialized.position = launched.position;
      specialized.direction = this.launchDirection;
      console.log(specialized.toString() + ' advancing toward ' + JSON.stringify(launched.advanceTarget));
      specialized.advanceTarget = launched.advanceTarget;
      this.movables.push(specialized);

      this.launchDirection = null;
      this.specialization = null;
      
      this.advancing = true; // advance one space until the new head meets the advanceTarget
    }
  },

  maybeDeploy: function () {
    // if there are remaining bots, deploy
    if (this.deployed && this.advancing && this.numberToDeploy >= 0) {
      var deployed = Object.create(
        this.numberToDeploy === 0 ? CabooseBot : GenericBot);
      deployed.position = this.levelInfo.start;
      deployed.direction = this.deployDirection;

      // head is the front car
      if (!this.trainHead) {
        this.trainHead = deployed;
        this.trainHead.advanceTarget = this.launchTarget;
        this.launchTarget = null;
      } 
      // set up links from each car to the car behind it
      if (this.lastDeployed) {
        this.lastDeployed.trainPrevious = deployed;
      }
      if (this.numberToDeploy === 0) {
        this.trainCaboose = deployed;
      }

      this.movables.push(deployed);
      this.lastDeployed = deployed;
      this.numberToDeploy -= 1;
    }
  },

  calculatePaths: function() {
    var that = this;

    var maybeChangeDirection = function (cell, currentDirection) {
      var arrow = cell.tiles.filter(
        function (tile) { return tile.type === 'arrow'; })[0];
      return arrow ? arrow.direction : currentDirection;
    };
    
    var applyToPathHelper = function applyToPathHelper(position, direction, turns, property, value) {
      var cell,
      newdirection;
      if (position.row >= 0 && position.row < that.board.height()
          && position.col >= 0 && position.col < that.board.width()) {
        cell = that.board.cellAt(position);
        if (cell.anyTilesOfType('wall')) {
          // terminate
        }
        else {
          if (!cell[property]) {
            cell[property] = value;
          }
          newdirection = maybeChangeDirection(cell, direction);
          if (newdirection !== direction) {
            turns -= 1;
          }
          if (turns >= 0) {
            applyToPathHelper(
              UTIL.advance(position, newdirection), newdirection, turns, property, value);
          }
        }
      }
    };

    var applyToPath = function (position, direction, property, value) {
      for (var turns = 0 ; turns <= 3 ; turns += 1) {
        applyToPathHelper(position, direction, turns, property, value);
      }
    };

    var applyToPathAllDirs = function (position, property) {
      // we want to apply all 0-turns first, then all 1-turns, etc.
      for (var turns = 0 ; turns <= 3 ; turns += 1) {
        // final value is the initial direction. The path direction might change
        // but the initial direction should not
        applyToPathHelper(UTIL.advance(position, 'up'), 'up', turns, property, 'up');
        applyToPathHelper(UTIL.advance(position, 'down'), 'down',turns, property, 'down');
        applyToPathHelper(UTIL.advance(position, 'left'), 'left', turns, property, 'left');
        applyToPathHelper(UTIL.advance(position, 'right'), 'right', turns, property, 'right');
      }
    };
    
    // clear path status
    this.board.forEachCell(
      function (position, cell) {
        cell.onTrainPath = null;
        cell.onLaunchPath = null;
      });
    
    // path starts in all directions from the start position 
    if (!this.deployed) {
      applyToPathAllDirs(this.levelInfo.start, 'onTrainPath');
    }
    else if (this.trainHead) {
      if (this.specialization) {
        applyToPathAllDirs(this.trainHead.position, 'onLaunchPath');
      }
      else {
        applyToPath(UTIL.advance(this.trainHead.position,
                                 this.trainHead.direction),
                    this.trainHead.direction, 'onTrainPath', this.trainHead.direction);
      }
    }
  },
  
  // TODO finish the walk before dying
  checkGameOver: function () {
    var res;
    if (!this.gameOver) {
      if (this.won) {
        res = confirm('Your robotrain is unstoppable!\nPress OK to go to the next level');
        this.gameOver = true;
        if (res) {
          console.log("going to the next level: " + (this.currentLevelIdx + 1));
          loadLevel(this.currentLevelIdx + 1);
        }
        else {
          loadLevel(this.currentLevelIdx);
        }
      }
      else if (this.lost) {
        alert('Level Failed!');
        this.gameOver = true;
        loadLevel(this.currentLevelIdx);
      }
    }
  }
};


var UTIL = {
  loadAsset: function (assetUrl, callback, type) {
    var req = new XMLHttpRequest();
    req.open("GET", assetUrl, true);
    if (type) {
      req.responseType = type;
    }
    if (callback) {
      req.onload = function () { callback(req); };
    }
    req.send();
  },

  bind: function (scope, fn) {
    return function () {
      fn.apply(scope, arguments);
    };
  },

  advance: function (position, direction) {
    if (direction === 'up') {
      return { row: position.row - 1, col: position.col };
    } else if (direction === 'down') {
      return { row: position.row + 1, col: position.col };
    } else if (direction === 'left') {
      return { row: position.row, col: position.col - 1 };
    } else if (direction === 'right') {
      return { row: position.row, col: position.col + 1 };
    }
    return position;
  },

  positionsEqual: function (pos1, pos2) {
    return pos1.row === pos2.row && pos1.col === pos2.col;
  },

  callbackAfterCountdown: function (counter, callback) {
    return function () {
      counter -= 1;
      if (counter === 0 && callback) { callback(); }
    };
  },
  
  inBounds: function (rect, point) {
    return point.x >= rect.x && point.x < rect.x + rect.w
      && point.y >= rect.y && point.y < rect.y + rect.h;
  }

};

var currentGame = null;

function loadLevel(levelIdx) {
  if (levelIdx === undefined) {
    levelIdx = sessionStorage.getItem('level');
  }
  else {
    sessionStorage.setItem('level', levelIdx);
  }

  if (LEVELS[levelIdx] === undefined) {
    levelIdx = 0;
  }


  if (currentGame) {
    currentGame.stop();
  }
  currentGame = Object.create(Game).init(levelIdx);
}

window.onload = function () {
  IMAGE_CACHE.init(
    // callback
    loadLevel);
};




// http://answers.oreilly.com/topic/1929-how-to-use-the-canvas-and-draw-elements-in-html5/
var relMouseCoords = function (evt){
  var x;
  var y;
  if (evt.pageX || evt.pageY) {
    x = evt.pageX;
    y = evt.pageY;
  } else {
    x = evt.clientX + document.body.scrollLeft +
      document.documentElement.scrollLeft;
    y = evt.clientY + document.body.scrollTop +
      document.documentElement.scrollTop;
  }
  x -= this.offsetLeft;
  y -= this.offsetTop;
  return { x: x, y: y };
};
HTMLCanvasElement.prototype.relMouseCoords = relMouseCoords;

if (!Object.create) {
  Object.create = function (o) {
    if (arguments.length > 1) {
      throw new Error(
        'Object.create implementation only accepts the first parameter.');
    }
    function F() {}
    F.prototype = o;
    return new F();
  };
}

if (!Array.prototype.removeIf) {
  Array.prototype.removeIf = function(pred) {
    var removed = false;
    for (var ii = this.length - 1; ii >= 0 ; ii -= 1) {
      if (pred(this[ii])) {
        this.splice(ii, 1);
        removed = true;
      }
    }
    return removed;
  };
}

if (!Object.prototype.forEachEntry) {
  Object.prototype.forEachEntry = function (fn) {
    for (var key in this) {
      if (this.hasOwnProperty(key)) {
        fn(key, this[key]);
      }
    }
  };
}
