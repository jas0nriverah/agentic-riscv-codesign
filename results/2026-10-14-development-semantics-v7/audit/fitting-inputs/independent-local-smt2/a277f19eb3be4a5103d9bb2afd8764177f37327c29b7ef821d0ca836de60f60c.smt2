(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x41 (bvadd independent_opaque_1 (_ bv2047 32))))
(let ((?x13 (bvadd independent_opaque_0 ?x41)))
(let ((?x17 (bvadd ?x41 independent_opaque_0)))
(and (distinct ?x17 ?x13) true)))))
(check-sat)
