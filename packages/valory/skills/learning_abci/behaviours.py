# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This package contains round behaviours of LearningAbciApp."""

from abc import ABC
from typing import Generator, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.learning_abci.models import Params, SharedState
from packages.valory.skills.learning_abci.payloads import (
    APICheckPayload,
    SendDataToIPFSPayload,
    DecisionMakingPayload,
    TxPreparationPayload,
    MultisendTxPreparationPayload,
)
from packages.valory.skills.learning_abci.rounds import (
    APICheckRound,
    SendDataToIPFSRound,
    DecisionMakingRound,
    Event,
    LearningAbciApp,
    SynchronizedData,
    TxPreparationRound,
    MultisendTxPreparationRound,
)

# Added by Ivan
import json
from typing import Any, Dict, List, Optional
from packages.valory.contracts.gnosis_safe.contract import (
    GnosisSafeContract,
    SafeOperation,
)
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.io_.store import SupportedFiletype
from packages.valory.skills.transaction_settlement_abci.rounds import TX_HASH_LENGTH
from packages.valory.skills.transaction_settlement_abci.payload_tools import (
    hash_payload_to_hex,
)
from packages.valory.contracts.multisend.contract import (
    MultiSendContract,
)
from pathlib import Path
from tempfile import mkdtemp

HTTP_OK = 200
GNOSIS_CHAIN_ID = "gnosis"
TX_DATA = b"0x"
SAFE_GAS = 0
VALUE_KEY = "value"
TO_ADDRESS_KEY = "to_address"

HTTP = "http://"
HTTPS = HTTP[:4] + "s" + HTTP[4:]
IPFS_ADDRESS = f"{HTTPS}gateway.autonolas.tech/ipfs/"
METADATA_FILENAME = "metadata.json"
ETHER_VALUE = 0
ZERO_ETHER_VALUE = 0


class LearningBaseBehaviour(BaseBehaviour, ABC):  # pylint: disable=too-many-ancestors
    """Base behaviour for the learning_abci skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

    @property
    def local_state(self) -> SharedState:
        """Return the state."""
        return cast(SharedState, self.context.state)


class APICheckBehaviour(LearningBaseBehaviour):  # pylint: disable=too-many-ancestors
    """APICheckBehaviour"""

    matching_round: Type[AbstractRound] = APICheckRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            price = yield from self.get_price()
            payload = APICheckPayload(sender=sender, price=price)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_price(self):
        """Get token price from Coingecko"""

        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&x_cg_demo_api_key=CG-8TNdtWrUiXbxDPQ1MYsoy6wU"

        header = {"accept": "application/json"}

        result = yield from self.get_http_response(method='GET', url=url, headers=header)

        str_data = result.body.decode()
        data = json.loads(str_data)
                     
        if result is None:
            price = 0.0
        else:
            price = data['bitcoin']['usd']

        self.context.logger.info(f"Price is {price}")
        return price
    

class SendDataToIPFSBehaviour(LearningBaseBehaviour):  # pylint: disable=too-many-ancestors
    """SendDataToIPFSBehaviour"""

    matching_round: Type[AbstractRound] = SendDataToIPFSRound

    @property
    def metadata_filepath(self) -> str:
        """Get the filepath to the metadata."""
        return str(Path(mkdtemp()) / METADATA_FILENAME)

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            data = yield from self.get_stablecoin_prices()
            data_hash = yield from self.send_data_to_ipfs(data)
            payload = SendDataToIPFSPayload(sender=sender, ipfs_hash=data_hash)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_stablecoin_prices(self):
        """Get stablecoin price from Coingecko"""

        url = "https://api.coingecko.com/api/v3/simple/price?ids=usd-coin%2Ctether%2Cdai%2Cusdd%2Cethena-usde%2Cusdb&vs_currencies=usd&x_cg_api_key=CG-8TNdtWrUiXbxDPQ1MYsoy6wU"

        header = {"accept": "application/json"}

        result = yield from self.get_http_response(method='GET', url=url, headers=header)

        str_data = result.body.decode()
        data = json.loads(str_data)

        self.context.logger.info(f"Stablecoin data is {data}")
        return data

    def send_data_to_ipfs(self, data):
         """Send Mech metadata to IPFS."""
         data_hash = yield from self.send_to_ipfs(
             self.metadata_filepath, data, filetype=SupportedFiletype.JSON
         )

         return data_hash


class DecisionMakingBehaviour(
    LearningBaseBehaviour
):  # pylint: disable=too-many-ancestors
    """DecisionMakingBehaviour"""

    matching_round: Type[AbstractRound] = DecisionMakingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            event = yield from self.get_event()
            payload = DecisionMakingPayload(sender=sender, event=event)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_event(self):
        """Get the next event"""
        # Using the token price from the previous round, decide whether we should make a transfer or not

        data = yield from self.get_ipfs_data()

        self.context.logger.info(f"Data loaded from IPFS is {data}")

        self.context.logger.info(f"Stored IPFS hash is {self.synchronized_data.ipfs_hash}")

        if self.synchronized_data.price <= 0.0:
            event = Event.DONE.value
        else:
            average_price = self.get_stablecoin_average_price(data)
            self.context.logger.info(f"Average stablecoin price is {average_price}")
            if average_price > 0.99:
                event = Event.MULTISEND_TRANSACT.value
            else:
                event = Event.TRANSACT.value
        self.context.logger.info(f"Event is {event}")
        return event
    
    def get_ipfs_data(self) -> Any:
        data = yield from self.get_from_ipfs(self.synchronized_data.ipfs_hash, filetype=SupportedFiletype.JSON)

        return data
    
    def get_stablecoin_average_price(self, coin_data):
        total = 0.0
        for coin in coin_data:
            total += coin_data[coin]["usd"]

        return total / len(coin_data)


class TxPreparationBehaviour(
    LearningBaseBehaviour
):  # pylint: disable=too-many-ancestors
    """TxPreparationBehaviour"""

    matching_round: Type[AbstractRound] = TxPreparationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            tx_hash = yield from self.get_tx_hash()
            payload = TxPreparationPayload(
                sender=sender, tx_submitter=None, tx_hash=tx_hash
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_tx_hash(self):
        """Get the tx hash"""
        # We need to prepare a 1 wei transfer from the safe to another (configurable) account.
        call_data = {VALUE_KEY: 1, TO_ADDRESS_KEY: self.params.transfer_target_address}

        safe_tx_hash = yield from self._build_safe_tx_hash(**call_data)
        if safe_tx_hash is None:
            self.context.logger.error("Could not build the safe transaction's hash.")
            return None

        tx_hash = hash_payload_to_hex(
            safe_tx_hash,
            call_data[VALUE_KEY],
            SAFE_GAS,
            call_data[TO_ADDRESS_KEY],
            TX_DATA,
        )

        return tx_hash
    
    def _build_safe_tx_hash(
        self, **kwargs: Any
    ) -> Generator[None, None, Optional[str]]:
        """Prepares and returns the safe tx hash for a multisend tx."""
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            data=TX_DATA,
            safe_tx_gas=SAFE_GAS,
            chain_id=GNOSIS_CHAIN_ID,
            **kwargs,
        )

        if response_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                "Couldn't get safe tx hash. Expected response performative "
                f"{ContractApiMessage.Performative.STATE.value!r}, "  # type: ignore
                f"received {response_msg.performative.value!r}: {response_msg}."
            )
            return None

        tx_hash = response_msg.state.body.get("tx_hash", None)
        if tx_hash is None or len(tx_hash) != TX_HASH_LENGTH:
            self.context.logger.error(
                "Something went wrong while trying to get the buy transaction's hash. "
                f"Invalid hash {tx_hash!r} was returned."
            )
            return None

        # strip "0x" from the response hash
        return tx_hash[2:]
    

class MultisendTxPreparationBehaviour(
    LearningBaseBehaviour
):  # pylint: disable=too-many-ancestors
    """MultisendTxPreparationBehaviour"""

    matching_round: Type[AbstractRound] = MultisendTxPreparationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            tx_hash = yield from self.get_tx_hash()
            payload = MultisendTxPreparationPayload(
                sender=sender, tx_submitter=None, muiltisend_tx_hash=tx_hash
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_tx_hash(self):
        """Get the tx hash"""
        # We need to prepare a 1 wei transfer from the safe to another (configurable) account.
        call_data = {VALUE_KEY: 1, TO_ADDRESS_KEY: self.params.transfer_target_address}

        safe_tx_hash = yield from self.get_multisend_hash()
        if safe_tx_hash is None:
            self.context.logger.error("Could not build the safe transaction's hash.")
            return None

        tx_hash = hash_payload_to_hex(
            safe_tx_hash,
            call_data[VALUE_KEY],
            SAFE_GAS,
            call_data[TO_ADDRESS_KEY],
            TX_DATA,
        )

        return tx_hash

    
    def get_multisend_hash(self) -> Generator[None, None, Optional[str]]:
        """Transform payload to MultiSend."""
        multi_send_txs = []

        transaction1 = {
            "operation": SafeOperation.DELEGATE_CALL.value,
            "to": self.synchronized_data.safe_contract_address,
            "value": 0,
            "data": TX_DATA,
        }
        transaction2 = {
            "operation": SafeOperation.DELEGATE_CALL.value,
            "to": self.synchronized_data.safe_contract_address,
            "value": 0,
            "data": TX_DATA,
        }
        transaction3 = {
            "operation": SafeOperation.DELEGATE_CALL.value,
            "to": self.synchronized_data.safe_contract_address,
            "value": 0,
            "data": TX_DATA,
        }

        multi_send_txs.append(transaction1)
        multi_send_txs.append(transaction2)
        multi_send_txs.append(transaction3)

        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(MultiSendContract.contract_id),
            contract_callable="get_tx_data",
            multi_send_txs=multi_send_txs,
        )
        if response.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(
                f"Couldn't compile the multisend tx. "
                f"Expected performative {ContractApiMessage.Performative.RAW_TRANSACTION.value}, "  # type: ignore
                f"received {response.performative.value}."
            )
            return None

        # strip "0x" from the response
        multisend_data_str = cast(str, response.raw_transaction.body["data"])[2:]
        tx_data = bytes.fromhex(multisend_data_str)
        tx_hash = yield from self._get_safe_tx_hash(tx_data)
        if tx_hash is None:
            # something went wrong
            return None

        return tx_hash

    
    def _get_safe_tx_hash(self, data: bytes) -> Generator[None, None, Optional[str]]:
        """
        Prepares and returns the safe tx hash.

        This hash will be signed later by the agents, and submitted to the safe contract.
        Note that this is the transaction that the safe will execute, with the provided data.

        :param data: the safe tx data.
        :return: the tx hash
        """
        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            to_address=self.params.transfer_target_address,  # we send the tx to the multisend address
            value=ZERO_ETHER_VALUE,
            data=data,
            safe_tx_gas=SAFE_GAS,
            operation=SafeOperation.DELEGATE_CALL.value,
        )

        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"Couldn't get safe hash. "
                f"Expected response performative {ContractApiMessage.Performative.STATE.value}, "  # type: ignore
                f"received {response.performative.value}."
            )
            return None

        # strip "0x" from the response hash
        tx_hash = cast(str, response.state.body["tx_hash"])[2:]
        return tx_hash


class LearningRoundBehaviour(AbstractRoundBehaviour):
    """LearningRoundBehaviour"""

    initial_behaviour_cls = APICheckBehaviour
    abci_app_cls = LearningAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [  # type: ignore
        APICheckBehaviour,
        SendDataToIPFSBehaviour,
        DecisionMakingBehaviour,
        TxPreparationBehaviour,
        MultisendTxPreparationBehaviour,
    ]
