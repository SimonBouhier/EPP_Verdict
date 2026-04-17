import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { Epp } from "../target/types/epp";
import { expect } from "chai";

describe("epp", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const program = anchor.workspace.Epp as Program<Epp>;

  it("Ping -- programme alive", async () => {
    const tx = await program.methods.ping().rpc();
    console.log("Ping tx:", tx);
  });
});
