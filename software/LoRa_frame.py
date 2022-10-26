configs = { # bytes,precision
        'temp' : (2, 0.1   ),
        'pres' : (2, 0.1   ),
        'humi' : (1, 0.5   ),
        'voc'  : (2, 0.1   ),
        'uv'   : (2, 1     ),
        'lx'   : (2, 1     ),
        'volu' : (1, 0.5   ),
        'batt' : (2, 0.01  ),
        'co2'  : (2, 0.1   ),
        'pm25' : (2, 0.1   ),
        'pm10' : (2, 0.1   ),
        'lat'  : (4, 0.0001),
        'long' : (4, 0.0001),
        'alt'  : (2, 0.01  ),
        'fw'   : (1, 1     ),
}

def pack(name, values):
    numbytes, precision  = configs[name]
    value = round(values / precision)                       # round to precision
    value = max(0, min(value, 2**(8*numbytes) - 1))         # stay in range 0 .. int.max_size - 1
    out = value.to_bytes(numbytes, 'big')                   # pack to bytes
    return out

def make_frame(data_odict):
    frame = bytes([])
    for key, values in data_odict.items():
        frame += pack(key, values)
    return frame