(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x76 (bvadd independent_opaque_0 (_ bv31 32))))
(let ((?x305 (bvadd (bvadd independent_opaque_0 (_ bv16 32)) (_ bv15 32))))
(and (distinct ?x305 ?x76) true))))
(check-sat)
