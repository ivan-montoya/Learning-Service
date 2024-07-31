## Autonolas Dev Academy - Final Assignment

Author: Ivan Montoya
Email: montoyaivan7.2@gmail.com

As a disclaimer, I'd like to clarify that due to software constraints, I was only able to code this assignment to be functional with a single agent. For the final assignment, I have implemented sending and getting data from IPFS, as well as using multisend transactions. For this assignment, I have added the behaviors SendDataToIPFSBehaviour and MultisendTxPreparationBehavior. Additionally, I have modified DecisionMakingBehaviour.

1. Use IPFS to store large amounts of data:

For my implementation, I use SendDataToIPFSBehaviour to query the CoinGecko API for the current price of multiple stablecoins, such as USDC and USDT, to name a few. That data is retreived as a dictionary and sent to IPFS.

DecisionMakingBehaviour is then utitlized to retrieve this information from IPFS. It calculates the average stablecoin price and uses this information to make a decision on which transaction type to use. If the average stablecoin price is greater than 0.99, then a Multisend transaction with be used. Otherwise, a regular transaction will be used.

2. Use multisend transactions:

Quite frankly, I don't really understand how multisend transactions work in a theoretical sense, but implemented it to the best of my knowledge and in the simplest form while still complying with the requirements for the final assignment. MultisendTxPreparationBehaviour is where this is implemented. The idea here was to make 3 hard-coded copies of the transaction used in TxPreparationBehaviour to prepare the multisend transaction. It creates the multisend transaction hash, and from there, the hash is utilized in the exact same way as the hash constructed in TxPreparationBehaviour