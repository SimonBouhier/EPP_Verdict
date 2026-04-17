import Formal.Basic
import Formal.TierBoundary

#eval assignTier (⟨5000, by omega⟩ : Score) 5 true
#eval assignTier (⟨9000, by omega⟩ : Score) 1 false
#eval assignTier (⟨9000, by omega⟩ : Score) 3 false
