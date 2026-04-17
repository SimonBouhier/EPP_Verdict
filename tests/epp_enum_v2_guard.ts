import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { Epp } from "../target/types/epp";
import { expect } from "chai";

describe("Enum V2 guard", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const program = anchor.workspace.Epp as Program<Epp>;

  const submitter = anchor.web3.Keypair.generate();

  before(async () => {
    const sig = await provider.connection.requestAirdrop(
      submitter.publicKey,
      2 * anchor.web3.LAMPORTS_PER_SOL
    );
    const latest = await provider.connection.getLatestBlockhash();
    await provider.connection.confirmTransaction(
      {
        signature: sig,
        blockhash: latest.blockhash,
        lastValidBlockHeight: latest.lastValidBlockHeight,
      },
      "confirmed"
    );
  });

  it("rejects epistemic_type = 3 with InvalidEpistemicType", async () => {
    const claimHashBytes = new Uint8Array(32);
    claimHashBytes.fill(7);
    const claimHash = Array.from(claimHashBytes);

    const [attestationPda] = anchor.web3.PublicKey.findProgramAddressSync(
      [
        Buffer.from("attestation"),
        submitter.publicKey.toBuffer(),
        Buffer.from(claimHashBytes),
      ],
      program.programId
    );

    const subject = Array(64).fill(0);
    subject[0] = "s".charCodeAt(0);
    const predicate = Array(64).fill(0);
    predicate[0] = "p".charCodeAt(0);
    const objectBytes = Array(128).fill(0);
    objectBytes[0] = "o".charCodeAt(0);
    const frameHash = Array(32).fill(0);
    const sourceAnchorBytes = Array(32).fill(0);

    let txSucceeded = false;
    let caughtError: any = null;

    try {
      await program.methods
        .submitAttestation(
          claimHash,
          subject,
          predicate,
          objectBytes,
          5000,
          3,
          3,
          5000,
          5000,
          5000,
          5000,
          5000,
          3,
          1,
          frameHash,
          sourceAnchorBytes,
          new anchor.BN(1_700_000_000),
          0,
          1,
          false,
          anchor.web3.PublicKey.default
        )
        .accounts({
          attestation: attestationPda,
          submitter: submitter.publicKey,
          systemProgram: anchor.web3.SystemProgram.programId,
        } as any)
        .signers([submitter])
        .rpc();
      txSucceeded = true;
    } catch (err) {
      caughtError = err;
    }

    if (txSucceeded) {
      expect.fail(
        "Expected transaction to fail with InvalidEpistemicType, but it succeeded."
      );
    }

    let anchorError: anchor.AnchorError | null = null;
    if (caughtError instanceof anchor.AnchorError) {
      anchorError = caughtError;
    } else if (caughtError && caughtError.logs) {
      anchorError = anchor.AnchorError.parse(caughtError.logs);
    }

    if (!anchorError) {
      throw caughtError;
    }

    expect(anchorError.error.errorCode.code).to.equal("InvalidEpistemicType");
    expect(anchorError.error.errorCode.number).to.equal(6006);
  });
});
