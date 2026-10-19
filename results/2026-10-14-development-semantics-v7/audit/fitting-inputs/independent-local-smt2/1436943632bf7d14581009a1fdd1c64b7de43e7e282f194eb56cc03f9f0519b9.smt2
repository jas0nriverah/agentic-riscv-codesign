(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x15 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv2072 32)))))
(let ((?x37 (bvadd (bvadd (bvadd independent_opaque_1 (_ bv2047 32)) independent_opaque_0) (_ bv25 32))))
(and (distinct ?x37 ?x15) true))))
(check-sat)
