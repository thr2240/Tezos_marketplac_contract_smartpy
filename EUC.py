import smartpy as sp

class EUC(sp.Contract):
    def __init__(self, creator, buyer, escrowToken):
        self.init(
            creator=creator,
            buyer=buyer,
            escrowToken=escrowToken,
            escrowAmount=sp.nat(0),
            escrowTokenId=sp.nat(0),
            strikePrice=sp.mutez(0),
            expireTime=sp.timestamp(0),
            fee=sp.nat(0),
            paused=False,
        )

    @sp.entry_point
    def init_option(self, params):
        self.data.creator = params.creator
        self.data.escrowToken = params.escrowToken
        self.data.escrowAmount = params.escrowAmount
        self.data.escrowTokenId = params.escrowTokenId
        self.data.strikePrice = params.strikePrice
        self.data.expireTime = params.expireTime
        self.data.fee = params.fee

        sp.verify(~self.data.paused,
                  "Contract is not accepting New Option Orders")

        # deposit escrow token to the contract
        _params = [
                sp.record(from_=sp.sender,
                                       txs=[
                                           sp.record(to_=sp.self_address,
                                                     amount=params.escrowAmount,
                                                     token_id=params.escrowTokenId)
                                       ])
            ]
        self.transfer_token(params.escrowToken, _params)
        sp.emit(sp.record(creator=params.creator), tag="INIT_OPTION")

    @sp.entry_point
    def buy_option(self):
        
        # check deposit amount
        expected_value = self.data.escrowAmount * sp.utils.mutez_to_nat(self.data.strikePrice)
        sp.verify(sp.utils.nat_to_mutez(expected_value) == sp.amount, "Insufficient Amount")
        
        # send premieum to the creator
        _params = [
                sp.record(from_=sp.sender,
                                       txs=[
                                           sp.record(to_=self.data.creator,
                                                     amount=self.data.fee,
                                                     token_id=self.data.escrowTokenId)
                                       ])
            ]
        self.transfer_token(self.data.escrowToken, _params)

        self.data.buyer = sp.sender
        self.data.paused = True
        sp.emit(sp.record(buyer=self.data.buyer), tag="BUY_OPTION")

    @sp.entry_point
    def execute_option(self, price):
        sp.set_type(price, sp.TMutez)

        # check expire time
        sp.verify(sp.now >= self.data.expireTime, "NOT EXPIRED")
        sp.verify(self.data.paused, "Not Created")
        Amount = sp.local("Amount", sp.utils.mutez_to_nat(self.data.strikePrice) *
                          self.data.escrowAmount)

        sp.if self.data.strikePrice > price:
            # send strikePrice * escrowAmount to buyer
            sp.send(self.data.buyer, sp.utils.nat_to_mutez(Amount.value))

            # send escrow-token to seller
            _params = [
                sp.record(from_=sp.self_address,
                                       txs=[
                                           sp.record(to_=self.data.creator,
                                                     amount=self.data.escrowAmount,
                                                     token_id=self.data.escrowTokenId)
                                       ])
            ]
            self.transfer_token(self.data.escrowToken, _params)
        sp.else:
            # send strikePrice * escrowAmount to seller
            sp.send(self.data.creator, sp.utils.nat_to_mutez(Amount.value))

            # send escrow-token to buyer
            _params = [
                sp.record(from_=sp.self_address,
                                       txs=[
                                           sp.record(to_=self.data.buyer,
                                                     amount=self.data.escrowAmount,
                                                     token_id=self.data.escrowTokenId)
                                       ])
            ]
            self.transfer_token(self.data.escrowToken, _params)
        self.data.paused = False
    
    def transfer_token(self, contract, params_):
        sp.set_type(contract, sp.TAddress)
        sp.set_type(params_, sp.TList(
                sp.TRecord(
                    from_ = sp.TAddress, 
                    txs = sp.TList(
                        sp.TRecord(
                            amount = sp.TNat, 
                            to_ = sp.TAddress, 
                            token_id = sp.TNat
                        ).layout(("to_", ("token_id", "amount")))
                    )
                )
            .layout(("from_", "txs"))))
        contractParams = sp.contract(sp.TList(
                sp.TRecord(
                    from_ = sp.TAddress, 
                    txs = sp.TList(
                        sp.TRecord(
                            amount = sp.TNat, 
                            to_ = sp.TAddress, 
                            token_id = sp.TNat
                        ).layout(("to_", ("token_id", "amount")))
                    )
                )
            .layout(("from_", "txs"))), contract, entry_point="transfer").open_some()
        sp.transfer(params_, sp.mutez(0), contractParams)

@sp.add_test(name="EuropeanCallOption")
def test():
    sc = sp.test_scenario()
    sc.h1("EuropeanCallOption")
    seller = sp.test_account("Administrator")
    buyer = sp.test_account("Alice")
    escrowToken = sp.address("KT1AFA2mwNUMNd4SsujE1YYp29vd8BZejyKW")
    sc.h1("Full test")
    eu_contract = EUC(seller.address, buyer.address, escrowToken)
    sc += eu_contract
    
    sc.h2("Init Option")
    sc += eu_contract.init_option(sp.record(
        creator=seller.address,
        buyer=buyer.address,
        escrowToken=escrowToken,
        escrowAmount=sp.nat(10),
        escrowTokenId=sp.nat(0),
        strikePrice=sp.mutez(100),
        expireTime = sp.timestamp(10),
        fee=sp.nat(10),
        faTwoToken=False
    )).run(sender=seller.address)
    
    sc.h2("Buy Option")
    sc += eu_contract.buy_option().run(sender=buyer.address, amount=sp.mutez(1000))
    
    sc.h2("Execute Option")
    sc += eu_contract.execute_option( sp.mutez(20)).run(now=sp.timestamp(20))
    
    
    
