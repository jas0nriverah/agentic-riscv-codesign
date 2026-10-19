(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x306 (bvshl independent_opaque_0 (bvand (_ bv10 32) (_ bv31 32)))))
(let ((?x65 (bvadd ?x306 independent_opaque_1)))
(let ((?x10 (bvadd independent_opaque_1 ?x306)))
(and (distinct ?x10 ?x65) true)))))
(check-sat)
