(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x113 (bvadd (bvshl independent_opaque_1 (bvand (_ bv24 32) (_ bv31 32))) (_ bv18 32))))
(let ((?x24 (bvand (_ bv24 32) (_ bv31 32))))
(let ((?x72 (bvadd (bvshl independent_opaque_0 (bvand (_ bv31 32) (_ bv31 32))) independent_opaque_1)))
(let ((?x424 (bvadd (bvshl ?x72 ?x24) (_ bv18 32))))
(and (distinct ?x424 ?x113) true))))))
(check-sat)
