(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x116 (bvadd independent_opaque_1 (_ bv5 32))))
(let ((?x44 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv31 32) (_ bv31 32)))) ?x116)))
(let ((?x15 (bvshl independent_opaque_0 (bvand (_ bv31 32) (_ bv31 32)))))
(let ((?x38 (bvadd ?x116 ?x15)))
(and (distinct ?x38 ?x44) true))))))
(check-sat)
