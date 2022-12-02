import json

class RealtimeData():
    def __init__(self, data):

        if type(data) != dict:
            list_struct = ['timestamp', 'epoch',
                           'oracle_price', '1m', '5m', '1h', '4h']
            data = dict(zip(list_struct, data))

        self.data = data

        for key in self.data:
            try:
                number = int(key[0])
                self.data[key] = json.loads(self.data[key])
            except:
                continue

        self.__dict__.update(self.data)
