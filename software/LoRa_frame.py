configs = { # bytes, offset, precision
        'temp' : (2, 100, 0.01  ),
        'pres' : (2,   0, 0.1   ),
        'humi' : (1,   0, 0.5   ),
        'voc'  : (2,   0, 0.1   ),
        'uv'   : (2,   0, 1     ),
        'lx'   : (2,   0, 1     ),
        'volu' : (1,   0, 0.5   ),
        'batt' : (2,   0, 0.01  ),
        'co2'  : (2,   0, 0.1   ),
        'pm25' : (2,   0, 0.1   ),
        'pm10' : (2,   0, 0.1   ),
        'lat'  : (3,  90, 0.0001),
        'long' : (3, 180, 0.0001),
        'alt'  : (2, 100, 0.1   ),
        'hdop' : {1,   0, 0.01  },
        'fw'   : (1,   0, 1     ),
}

def pack(name, values):
    numbytes, offset, precision  = configs[name]
    value = round((values + offset) / precision)            # add offset, then round to precision
    value = max(0, min(value, 2**(8*numbytes) - 1))         # stay in range 0 .. int.max_size - 1
    out = value.to_bytes(numbytes, 'big')                   # pack to bytes
    return out

def make_frame(data_odict):
    frame = bytes([])
    for key, values in data_odict.items():
        frame += pack(key, values)
    return frame