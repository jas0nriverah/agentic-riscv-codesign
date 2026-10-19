(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x914 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (_ bv32 32))))
(let ((?x85 (bvsub (bvadd (_ bv0 32) (_ bv32 32)) independent_opaque_0)))
(and (distinct ?x85 ?x914) true))))
(check-sat)
