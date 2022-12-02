class BinanceCandle():
    def __init__(self, data):
        self.data = data

        self.openTime = self.data[0]
        self.openPrice = float(self.data[1])
        self.highPrice = float(self.data[2])
        self.lowPrice = float(self.data[3])
        self.closePrice = float(self.data[4])
        self.volume = float(self.data[5])
        self.closeTime = self.data[6]
        self.quoteAssetVolume = float(self.data[7])
        self.numberTrades = self.data[8]
        self.takerBuyBase = float(self.data[9])
        self.takerBuyQuote = float(self.data[10])
        self.ignore = self.data[11]