// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/// @dev SWC-107 — Classic reentrancy via checks-effects-interactions violation.
contract VulnerableVault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    /// @dev VULNERABLE: external call before state update (SWC-107)
    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        // External call BEFORE state update — reentrancy window
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");
        balances[msg.sender] -= amount;
    }

    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }
}
