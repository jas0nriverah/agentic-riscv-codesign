(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x42 (bvadd (bvshl independent_opaque_0 (bvand (_ bv5 32) (_ bv31 32))) (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32))))))
(let ((?x24 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x20 (bvadd (bvshl independent_opaque_0 (bvand (_ bv3 32) (_ bv31 32))) independent_opaque_1)))
(let ((?x843 (bvshl ?x20 ?x24)))
(and (distinct ?x843 ?x42) true))))))
(check-sat)
