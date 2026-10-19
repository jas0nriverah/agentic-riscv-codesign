(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x24 (bvshl independent_opaque_0 (bvand (_ bv21 32) (_ bv31 32)))))
(let ((?x65 (bvadd ?x24 independent_opaque_1)))
(let ((?x15 (bvadd independent_opaque_1 ?x24)))
(and (distinct ?x15 ?x65) true)))))
(check-sat)
