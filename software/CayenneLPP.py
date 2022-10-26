configs = {   # ID   bytes             precision
    'd_in'  : [  0,        1 ,                  1     ],
    'd_out' : [  1,        1 ,                  1     ],
    'a_in'  : [  2,        2 ,                  0.01  ],
    'a_out' : [  3,        2 ,                  0.01  ],
    'lumi'  : [101,        2 ,                  1     ],
    'presn' : [102,        1 ,                  1     ],
    'temp'  : [103,        2 ,                  0.1   ],
    'humi'  : [104,        1 ,                  0.5   ],
    'accel' : [113, [2, 2, 2], [0.001,  0.001,  0.001]],
    'baro'  : [115,        2 ,                  0.1   ],
    'gyro'  : [134, [2, 2, 2], [0.01,   0.01,   0.01 ]],
    'gps'   : [136, [4, 4, 2], [0.0001, 0.0001, 0.01 ]],
}

tags = {
    'temp' : 'temp',
    'pres' : 'baro',
    'humi' : 'humi',
    'voc'  : 'baro',
    'uv'   : 'lumi',
    'lx'   : 'lumi',
    'volu' : 'humi',
    'batt' : 'a_in',
    'co2'  : 'baro',
    'pm25' : 'baro',
    'pm10' : 'baro',
    'gps'  : 'gps',
    'fw'   : 'd_out',
}

def pack(name, values, lead, idx):
    tag = tags[name]
    cfg = configs[tag]
    id        = cfg[0]
    numbytes  = cfg[1]
    precision = cfg[2]

    out = bytes([])
    if lead > 0:
        if lead == 2:
            out += bytes([idx])
        out += bytes([id])

    if isinstance(values, int) or isinstance(values, float):    # pack single value
        value = int(values / precision)                         # round to precision
        value = max(0, min(value, 2**(8*numbytes) - 1))         # stay in range 0 .. int.max_size - 1
        out += value.to_bytes(numbytes, 'big')                  # pack to bytes
    elif isinstance(values, list):
        for i in range(len(values)):                            # pack each value in list
            value = int(values[i] / precision[i])               # round to precision
            value = max(0, min(value, 2**(8*numbytes[i]) - 1))  # stay in range 0 .. int.max_size - 1
            out += value.to_bytes(numbytes[i], 'big')           # pack to bytes
    return out

def make_frame(data_dict, lead = 0):
    frame = bytes([])
    for idx, key, values in enumerate(data_dict.items()):
        frame += pack(key, values, lead, idx)
    return frame