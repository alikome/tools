#!/usr/bin/env python3
"""
Bonk.fun Token Graduation Checker

This script checks if a bonk.fun (letsbonk.fun) token has graduated from the
bonding curve or shows the current bonding percentage if not graduated.

Uses Helius RPC to query the Solana blockchain.

Usage:
    python bonk_graduation_checker.py <TOKEN_MINT_ADDRESS> [--api-key YOUR_HELIUS_API_KEY]

Example:
    python bonk_graduation_checker.py 7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr
"""

import argparse
import json
import os
import struct
import sys
from base64 import b64decode
from hashlib import sha256

try:
    import requests
except ImportError:
    print("Error: 'requests' library is required. Install with: pip install requests")
    sys.exit(1)

try:
    from solders.pubkey import Pubkey
except ImportError:
    print("Error: 'solders' library is required. Install with: pip install solders")
    sys.exit(1)


# Bonk.fun (LetsBonk) program ID
BONK_PROGRAM_ID = Pubkey.from_string("LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj")

# Meteora Dynamic Bonding Curve program ID (underlying program)
METEORA_DBC_PROGRAM_ID = Pubkey.from_string("dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN")

# Initial token reserves for bonk.fun pools (based on research)
INITIAL_REAL_TOKEN_RESERVES = 793_100_000
TOKEN_DECIMALS = 6
SOL_DECIMALS = 9

# Graduation threshold - approximately 85 SOL worth in the bonding curve
GRADUATION_THRESHOLD_SOL = 85


class BonkGraduationChecker:
    """Check bonk.fun token graduation status and bonding curve progress."""

    def __init__(self, helius_api_key: str):
        """
        Initialize the checker with Helius API key.

        Args:
            helius_api_key: Your Helius API key
        """
        self.api_key = helius_api_key
        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={helius_api_key}"

    def _rpc_request(self, method: str, params: list) -> dict:
        """Make an RPC request to Helius."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }

        response = requests.post(
            self.rpc_url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            raise Exception(f"RPC Error: {result['error']}")

        return result.get("result")

    def derive_bonding_curve_pda(self, token_mint: Pubkey) -> Pubkey:
        """
        Derive the bonding curve PDA for a given token mint.

        The PDA is derived using seeds: ["pool", token_mint]
        """
        seeds = [b"pool", bytes(token_mint)]
        pda, _ = Pubkey.find_program_address(seeds, METEORA_DBC_PROGRAM_ID)
        return pda

    def get_account_info(self, pubkey: Pubkey) -> dict | None:
        """Fetch account info from the blockchain."""
        result = self._rpc_request(
            "getAccountInfo",
            [str(pubkey), {"encoding": "base64"}]
        )
        return result.get("value") if result else None

    def get_token_supply(self, token_mint: Pubkey) -> dict | None:
        """Get token supply information."""
        result = self._rpc_request("getTokenSupply", [str(token_mint)])
        return result.get("value") if result else None

    def get_token_accounts_by_owner(self, owner: Pubkey, mint: Pubkey) -> list:
        """Get token accounts owned by an address for a specific mint."""
        result = self._rpc_request(
            "getTokenAccountsByOwner",
            [
                str(owner),
                {"mint": str(mint)},
                {"encoding": "jsonParsed"}
            ]
        )
        return result.get("value", []) if result else []

    def parse_pool_account(self, data: bytes) -> dict:
        """
        Parse the Meteora DBC pool account data.

        Account structure (approximate based on research):
        - Discriminator (8 bytes)
        - Various config and state fields
        """
        if len(data) < 200:
            return {"error": "Account data too short"}

        # The account discriminator helps identify the account type
        discriminator = data[:8]

        # Parse key fields (offsets may need adjustment based on actual structure)
        # These are estimated based on similar bonding curve implementations
        parsed = {
            "discriminator": discriminator.hex(),
            "data_length": len(data),
        }

        return parsed

    def check_token_graduation(self, token_mint_str: str) -> dict:
        """
        Check if a bonk.fun token has graduated and get bonding curve progress.

        Args:
            token_mint_str: The token mint address as a string

        Returns:
            Dictionary with graduation status and bonding progress
        """
        try:
            token_mint = Pubkey.from_string(token_mint_str)
        except Exception as e:
            return {"error": f"Invalid token mint address: {e}"}

        result = {
            "token_mint": token_mint_str,
            "graduated": False,
            "bonding_percentage": 0.0,
            "status": "unknown",
            "details": {}
        }

        # Derive the bonding curve PDA
        pool_pda = self.derive_bonding_curve_pda(token_mint)
        result["details"]["pool_pda"] = str(pool_pda)

        # Fetch the pool account
        pool_account = self.get_account_info(pool_pda)

        if pool_account is None:
            # Pool doesn't exist - could mean:
            # 1. Token never was on bonk.fun
            # 2. Token has graduated and pool was closed
            result["status"] = "not_found"
            result["details"]["message"] = (
                "Pool account not found. Token may have graduated "
                "or was never launched on bonk.fun"
            )

            # Check if token exists at all
            token_info = self.get_token_supply(token_mint)
            if token_info:
                result["details"]["token_exists"] = True
                result["details"]["total_supply"] = token_info.get("uiAmountString", "unknown")

                # If pool is gone but token exists, likely graduated
                result["graduated"] = True
                result["bonding_percentage"] = 100.0
                result["status"] = "graduated"
                result["details"]["message"] = (
                    "Pool account closed - token has likely graduated to AMM"
                )
            else:
                result["details"]["token_exists"] = False
                result["details"]["message"] = "Token mint does not exist"

            return result

        # Pool account exists - token is still on bonding curve
        result["status"] = "on_bonding_curve"

        # Decode the account data
        account_data = b64decode(pool_account["data"][0])
        result["details"]["account_owner"] = pool_account.get("owner", "unknown")

        # Get token balance in the pool to calculate bonding progress
        token_accounts = self.get_token_accounts_by_owner(pool_pda, token_mint)

        if token_accounts:
            for acc in token_accounts:
                parsed = acc.get("account", {}).get("data", {}).get("parsed", {})
                info = parsed.get("info", {})
                token_amount = info.get("tokenAmount", {})

                if token_amount:
                    ui_amount = float(token_amount.get("uiAmount", 0))
                    amount = int(token_amount.get("amount", 0))

                    result["details"]["tokens_remaining"] = ui_amount
                    result["details"]["tokens_remaining_raw"] = amount

                    # Calculate bonding percentage
                    # Formula: 100 - ((remaining_tokens * 100) / initial_reserves)
                    if INITIAL_REAL_TOKEN_RESERVES > 0:
                        tokens_sold = INITIAL_REAL_TOKEN_RESERVES - (amount / (10 ** TOKEN_DECIMALS))
                        bonding_pct = (tokens_sold / INITIAL_REAL_TOKEN_RESERVES) * 100
                        bonding_pct = max(0, min(100, bonding_pct))  # Clamp to 0-100

                        result["bonding_percentage"] = round(bonding_pct, 2)

                        if bonding_pct >= 100:
                            result["graduated"] = True
                            result["status"] = "ready_to_graduate"
                            result["details"]["message"] = "Bonding curve complete, awaiting migration"
                        else:
                            result["details"]["message"] = f"{100 - bonding_pct:.2f}% remaining to graduation"

                    break

        # Also try to get SOL balance in the pool
        sol_balance = pool_account.get("lamports", 0)
        result["details"]["sol_in_pool"] = sol_balance / (10 ** SOL_DECIMALS)

        return result


def format_result(result: dict) -> str:
    """Format the result for display."""
    lines = []
    lines.append("=" * 60)
    lines.append("BONK.FUN TOKEN GRADUATION CHECK")
    lines.append("=" * 60)
    lines.append(f"Token Mint: {result['token_mint']}")
    lines.append("-" * 60)

    if "error" in result:
        lines.append(f"Error: {result['error']}")
    else:
        if result["graduated"]:
            lines.append("Status: GRADUATED")
            lines.append("Bonding Progress: 100%")
        else:
            lines.append(f"Status: {result['status'].upper().replace('_', ' ')}")
            lines.append(f"Bonding Progress: {result['bonding_percentage']:.2f}%")

            # Progress bar
            filled = int(result["bonding_percentage"] / 5)
            bar = "[" + "#" * filled + "-" * (20 - filled) + "]"
            lines.append(f"Progress Bar: {bar}")

        lines.append("-" * 60)
        lines.append("Details:")

        details = result.get("details", {})
        for key, value in details.items():
            if key != "message":
                lines.append(f"  {key}: {value}")

        if "message" in details:
            lines.append("-" * 60)
            lines.append(f"Note: {details['message']}")

    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Check if a bonk.fun token has graduated from the bonding curve",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bonk_graduation_checker.py 7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr
  python bonk_graduation_checker.py <TOKEN_MINT> --api-key YOUR_API_KEY

Environment Variables:
  HELIUS_API_KEY - Your Helius API key (alternative to --api-key)
        """
    )

    parser.add_argument(
        "token_mint",
        help="The token mint address to check"
    )

    parser.add_argument(
        "--api-key",
        default=os.environ.get("HELIUS_API_KEY"),
        help="Helius API key (or set HELIUS_API_KEY env variable)"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON"
    )

    args = parser.parse_args()

    if not args.api_key:
        print("Error: Helius API key is required.")
        print("Either set HELIUS_API_KEY environment variable or use --api-key flag")
        print("\nGet a free API key at: https://dev.helius.xyz/")
        sys.exit(1)

    checker = BonkGraduationChecker(args.api_key)
    result = checker.check_token_graduation(args.token_mint)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_result(result))


if __name__ == "__main__":
    main()
