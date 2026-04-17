// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/// @dev Simple onlyOwner access control pattern.
contract SimpleOwnable {
    address public owner;
    uint256 private storedValue;

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    function setOwner(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Zero address");
        owner = newOwner;
    }

    function setValue(uint256 value) external onlyOwner {
        storedValue = value;
    }

    function getValue() external view returns (uint256) {
        return storedValue;
    }

    function pause() external onlyOwner {
        // placeholder admin action
        storedValue = 0;
    }
}
